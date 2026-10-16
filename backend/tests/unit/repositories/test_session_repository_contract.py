"""SessionRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

세션은 users(id)를 FK로 가리키므로 SQL 구현에서는 사용자 행이 먼저 있어야 한다(fixture가 만든다).
사용자 삭제는 세션을 폐기(revoke)하지 않고 행을 지운다(delete_all_for_user).
"""

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio

from app.domain.auth.principal import Principal, Role
from app.domain.auth.session import AuthSession, SessionId
from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.domain.user.value_objects import UserId
from app.infra.db.session_repository import SqlSessionRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, later
from tests.factories_auth import make_principal
from tests.fakes.session_repository import FakeSessionRepository
from tests.support.database import rolled_back_session
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.session_repository import SessionRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
SESSION_USERS = ("kim", "lee", "S-1")  # fixture가 SQL에 만들어 두는 세션 소유 사용자(로그인 아이디)


def principal_of(name: str, role: Role = Role.SALES) -> Principal:
    """uid(name)을 user_id로 가진 주체. name은 SESSION_USERS 중 하나여야 SQL에서 FK가 맞는다."""
    return make_principal(name.lower(), role, user_id=uid(name.lower()))


def make_session(**overrides: object) -> AuthSession:
    values: dict[str, object] = {
        "id": SessionId(uuid4()),
        "principal": principal_of("kim", Role.ADMIN),
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=8),
    }
    return AuthSession(**{**values, **overrides})  # type: ignore[arg-type]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[SessionRepository]:
    if request.param == "fake":
        yield FakeSessionRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        await ensure_users(SqlUserRepository(session), *(uid(n.lower()) for n in SESSION_USERS))
        yield SqlSessionRepository(session)


async def test_add_then_get_by_token_hash_round_trips(repository: SessionRepository) -> None:
    session = make_session()
    await repository.add(session, "hash-1")

    stored = await repository.get_by_token_hash("hash-1")

    assert stored == session
    assert stored is not None
    assert stored.principal.user_id == session.principal.user_id
    assert stored.expires_at == session.expires_at
    assert stored.created_at == session.created_at
    assert stored.revoked_at is None


async def test_unknown_hash_returns_none(repository: SessionRepository) -> None:
    assert await repository.get_by_token_hash("nope") is None


async def test_duplicate_hash_is_rejected(repository: SessionRepository) -> None:
    await repository.add(make_session(), "same")

    with pytest.raises(AlreadyExistsError):
        await repository.add(make_session(), "same")


async def test_update_persists_revocation(repository: SessionRepository) -> None:
    session = make_session()
    await repository.add(session, "hash-1")
    session.revoke(later(30))

    await repository.update(session)

    stored = await repository.get_by_token_hash("hash-1")
    assert stored is not None
    assert stored.revoked_at == later(30)


async def test_update_unknown_session_raises_not_found(repository: SessionRepository) -> None:
    with pytest.raises(NotFoundError):
        await repository.update(make_session())


async def test_delete_all_for_user_removes_only_that_users_sessions(
    repository: SessionRepository,
) -> None:
    await repository.add(make_session(principal=principal_of("kim")), "kim-1")
    await repository.add(make_session(principal=principal_of("kim")), "kim-2")
    already = make_session(principal=principal_of("kim"))
    already.revoke(later(5))
    await repository.add(already, "kim-old")
    await repository.add(make_session(principal=principal_of("lee")), "lee-1")

    deleted = await repository.delete_all_for_user(uid("kim"))

    assert deleted == 3  # 이미 폐기된 세션 행도 지운다(행이 남으면 사용자 물리 삭제를 막는다)
    for token in ("kim-1", "kim-2", "kim-old"):
        assert await repository.get_by_token_hash(token) is None
    assert await repository.get_by_token_hash("lee-1") is not None


async def test_delete_all_for_user_without_sessions_returns_zero(
    repository: SessionRepository,
) -> None:
    assert await repository.delete_all_for_user(UserId(uuid4())) == 0
    assert await repository.delete_all_for_user(uid("lee")) == 0


async def test_deleted_sessions_cannot_be_updated_or_revived(
    repository: SessionRepository,
) -> None:
    session = make_session(principal=principal_of("kim"))
    await repository.add(session, "kim-1")
    await repository.delete_all_for_user(uid("kim"))

    with pytest.raises(NotFoundError):
        await repository.update(session)
    assert await repository.get_by_token_hash("kim-1") is None
