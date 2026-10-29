"""DirectorySettingsRepository 계약: 단일 행·revision 낙관적 잠금, 암호문·Base DN 왕복(AC3·AC5).

저장소는 암호화된 토큰 문자열만 다룬다(암호화는 application이 SecretCipher Port로 한다).
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from app.domain.common.secret import SealedSecret

from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import SecurityMode
from app.infra.db.directory_settings_repository import SqlDirectorySettingsRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, later
from tests.factories_auth import BASE_DN
from tests.factories_directory import make_directory_connection
from tests.fakes.directory_settings_repository import FakeDirectorySettingsRepository
from tests.support.database import rolled_back_session
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from app.application.ports.directory_settings_repository import DirectorySettingsRepository
    from app.domain.directory.settings import StoredDirectorySettings
    from app.domain.user.value_objects import UserId

SEALED = SealedSecret("gAAAAA-sealed-token-one")
SEALED_2 = SealedSecret("gAAAAA-sealed-token-two")

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[DirectorySettingsRepository]:
    if request.param == "fake":
        yield FakeDirectorySettingsRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        # updated_by는 users(id) FK라 저장자로 쓸 사용자 행이 먼저 있어야 한다
        await ensure_users(SqlUserRepository(session), uid("admin1"), uid("a"), uid("b"))
        yield SqlDirectorySettingsRepository(session)


async def _save(
    repository: DirectorySettingsRepository,
    *,
    expected_revision: int | None,
    now: datetime = NOW,
    updated_by: UserId | None = None,
    **overrides: object,
) -> StoredDirectorySettings:
    connection = make_directory_connection(
        **{k: v for k, v in overrides.items() if k not in {"sealed", "base_dn"}}
    )
    return await repository.save(
        connection,
        overrides.get("sealed", SEALED),  # type: ignore[arg-type]
        overrides.get("base_dn", BASE_DN),  # type: ignore[arg-type]
        expected_revision=expected_revision,
        updated_by=updated_by,
        now=now,
    )


async def test_empty_store_returns_none(repository: DirectorySettingsRepository) -> None:
    assert await repository.get() is None


async def test_first_save_creates_revision_one(repository: DirectorySettingsRepository) -> None:
    saved = await _save(repository, expected_revision=None)

    assert (saved.revision, saved.updated_at, saved.updated_by) == (1, NOW, None)
    assert await repository.get() == saved


async def test_first_save_when_row_exists_conflicts(
    repository: DirectorySettingsRepository,
) -> None:
    await _save(repository, expected_revision=None)

    with pytest.raises(DirectorySettingsConflictError):
        await _save(repository, expected_revision=None, base_dn="dc=other", now=later(5))

    stored = await repository.get()
    assert stored is not None
    assert (stored.revision, stored.base_dn) == (1, BASE_DN)


async def test_update_with_matching_revision_increments(
    repository: DirectorySettingsRepository,
) -> None:
    await _save(repository, expected_revision=None)

    updated = await _save(
        repository,
        expected_revision=1,
        base_dn="dc=new,dc=test",
        sealed=SEALED_2,
        updated_by=uid("admin1"),
        now=later(60),
    )

    assert (updated.revision, updated.updated_by, updated.updated_at) == (
        2,
        uid("admin1"),
        later(60),
    )
    stored = await repository.get()
    assert stored == updated
    assert stored is not None
    assert (stored.base_dn, stored.sealed_bind_password) == ("dc=new,dc=test", SEALED_2)


async def test_update_with_stale_revision_conflicts_and_keeps_row(
    repository: DirectorySettingsRepository,
) -> None:
    await _save(repository, expected_revision=None)
    await _save(
        repository, expected_revision=1, base_dn="dc=second", updated_by=uid("a"), now=later(1)
    )

    with pytest.raises(DirectorySettingsConflictError):
        await _save(
            repository, expected_revision=1, base_dn="dc=stale", updated_by=uid("b"), now=later(2)
        )

    stored = await repository.get()
    assert stored is not None
    assert (stored.revision, stored.base_dn, stored.updated_by) == (2, "dc=second", uid("a"))


async def test_update_without_existing_row_conflicts(
    repository: DirectorySettingsRepository,
) -> None:
    with pytest.raises(DirectorySettingsConflictError):
        await _save(repository, expected_revision=1, updated_by=uid("a"))

    assert await repository.get() is None


async def test_revision_keeps_counting_up(repository: DirectorySettingsRepository) -> None:
    await _save(repository, expected_revision=None)
    for expected in (1, 2, 3):
        saved = await _save(
            repository, expected_revision=expected, updated_by=uid("a"), now=later(expected)
        )

    assert saved.revision == 4


async def test_round_trip_keeps_all_fields(repository: DirectorySettingsRepository) -> None:
    long_token = SealedSecret("gAAAAA" + "x" * 400)
    await _save(
        repository,
        expected_revision=None,
        host="dc2.corp.test",
        port=3269,
        security=SecurityMode.STARTTLS,
        bind_account="CORP\\svc-sales",
        user_filter="(&(objectClass=user)(userPrincipalName={login_id}@corp.test))",
        connect_timeout_seconds=7,
        sealed=long_token,
        base_dn="ou=staff,dc=corp,dc=test",
    )

    stored = await repository.get()

    assert stored is not None
    assert stored.connection == make_directory_connection(
        host="dc2.corp.test",
        port=3269,
        security=SecurityMode.STARTTLS,
        bind_account="CORP\\svc-sales",
        user_filter="(&(objectClass=user)(userPrincipalName={login_id}@corp.test))",
        connect_timeout_seconds=7,
    )
    assert stored.sealed_bind_password == long_token  # 토큰 전체가 잘리지 않는다
    assert stored.base_dn == "ou=staff,dc=corp,dc=test"


@pytest.mark.parametrize(
    ("security", "port"),
    [(SecurityMode.NONE, 389), (SecurityMode.SSL, 636), (SecurityMode.STARTTLS, 389)],
)
async def test_every_security_mode_round_trips(
    repository: DirectorySettingsRepository, security: SecurityMode, port: int
) -> None:
    await _save(repository, expected_revision=None, security=security, port=port)

    stored = await repository.get()

    assert stored is not None
    assert (stored.connection.security, stored.connection.port) == (security, port)


@pytest.mark.parametrize("host", ["::1", "2001:db8::1", "10.0.0.5", "dc1"])
async def test_ip_literal_and_short_hosts_round_trip(
    repository: DirectorySettingsRepository, host: str
) -> None:
    await _save(repository, expected_revision=None, host=host)

    stored = await repository.get()

    assert stored is not None
    assert stored.connection.host == host


async def test_first_save_keeps_a_missing_saver_as_none(
    repository: DirectorySettingsRepository,
) -> None:
    await _save(repository, expected_revision=None)

    stored = await repository.get()

    assert stored is not None
    assert stored.updated_by is None
