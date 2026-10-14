"""DirectorySettingsRepository 계약(T-P18~P23): 단일 행과 revision 낙관적 잠금 (DS-6·7)."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import DirectoryUrl
from app.infra.db.directory_settings_repository import SqlDirectorySettingsRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, later
from tests.factories_auth import DUMMY_PEM, make_directory_settings
from tests.fakes.directory_settings_repository import FakeDirectorySettingsRepository
from tests.support.database import rolled_back_session
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.directory_settings_repository import DirectorySettingsRepository

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


async def test_empty_store_returns_none(repository: DirectorySettingsRepository) -> None:
    assert await repository.get() is None


async def test_first_save_creates_revision_one(repository: DirectorySettingsRepository) -> None:
    saved = await repository.save(
        make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
    )

    assert (saved.revision, saved.updated_at, saved.updated_by) == (1, NOW, None)
    assert await repository.get() == saved


async def test_first_save_when_row_exists_conflicts(
    repository: DirectorySettingsRepository,
) -> None:
    await repository.save(
        make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
    )

    with pytest.raises(DirectorySettingsConflictError):
        await repository.save(
            make_directory_settings(base_dn="dc=other"),
            expected_revision=None,
            updated_by=None,
            now=later(5),
        )

    stored = await repository.get()
    assert stored is not None
    assert (stored.revision, stored.settings.base_dn) == (1, "dc=corp,dc=test")


async def test_update_with_matching_revision_increments(
    repository: DirectorySettingsRepository,
) -> None:
    await repository.save(
        make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
    )

    updated = await repository.save(
        make_directory_settings(base_dn="dc=new,dc=test"),
        expected_revision=1,
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
    assert stored.settings.base_dn == "dc=new,dc=test"


async def test_update_with_stale_revision_conflicts_and_keeps_row(
    repository: DirectorySettingsRepository,
) -> None:
    await repository.save(
        make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
    )
    await repository.save(
        make_directory_settings(base_dn="dc=second"),
        expected_revision=1,
        updated_by=uid("a"),
        now=later(1),
    )

    with pytest.raises(DirectorySettingsConflictError):
        await repository.save(
            make_directory_settings(base_dn="dc=stale"),
            expected_revision=1,
            updated_by=uid("b"),
            now=later(2),
        )

    stored = await repository.get()
    assert stored is not None
    assert (stored.revision, stored.settings.base_dn, stored.updated_by) == (
        2,
        "dc=second",
        uid("a"),
    )


async def test_update_without_existing_row_conflicts(
    repository: DirectorySettingsRepository,
) -> None:
    with pytest.raises(DirectorySettingsConflictError):
        await repository.save(
            make_directory_settings(), expected_revision=1, updated_by=uid("a"), now=NOW
        )

    assert await repository.get() is None


async def test_revision_keeps_counting_up(repository: DirectorySettingsRepository) -> None:
    await repository.save(
        make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
    )
    for expected in (1, 2, 3):
        saved = await repository.save(
            make_directory_settings(),
            expected_revision=expected,
            updated_by=uid("a"),
            now=later(expected),
        )

    assert saved.revision == 4


async def test_round_trip_keeps_all_fields(repository: DirectorySettingsRepository) -> None:
    settings = make_directory_settings(
        server_urls=(
            DirectoryUrl.parse("ldap://dc2.corp.test:390"),
            DirectoryUrl.parse("ldaps://dc1.corp.test"),
            DirectoryUrl.parse("ldaps://[::1]:3269"),
        ),
        use_starttls=True,
        ca_cert_pem=DUMMY_PEM,
        bind_template="{login_id}@corp.test",
        base_dn="ou=staff,dc=corp,dc=test",
        user_filter="(&(objectClass=user)(userPrincipalName={login_id}@corp.test))",
        display_name_attribute="cn",
        email_attribute="userPrincipalName",
        connect_timeout_seconds=7,
        receive_timeout_seconds=33,
    )
    await repository.save(settings, expected_revision=None, updated_by=None, now=NOW)

    stored = await repository.get()

    assert stored is not None
    assert stored.settings == settings
    assert stored.settings.server_urls == settings.server_urls  # 순서 유지
    assert stored.settings.ca_cert_pem == DUMMY_PEM  # 줄바꿈 유지


async def test_round_trip_keeps_missing_ca_pem_as_none(
    repository: DirectorySettingsRepository,
) -> None:
    await repository.save(
        make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
    )

    stored = await repository.get()

    assert stored is not None
    assert stored.settings.ca_cert_pem is None
    assert stored.updated_by is None
