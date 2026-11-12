"""SessionRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

세션은 users(id)를 FK로 가리키므로 SQL 구현에서는 사용자 행이 먼저 있어야 한다(fixture가 만든다).
사용자 삭제는 세션을 폐기(revoke)하지 않고 행을 지운다(delete_all_for_user).
"""

from datetime import timedelta
from typing import TYPE_CHECKING

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
from tests.support.ids import new_id
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
        "id": SessionId(new_id()),
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
    """세션을 추가하고 토큰 해시로 조회하면 그대로 돌아온다."""
    # given: 세션
    session = make_session()
    # given: 세션을 해시와 함께 저장
    await repository.add(session, "hash-1")

    # when: 토큰 해시로 조회한다
    stored = await repository.get_by_token_hash("hash-1")

    # then: 저장한 세션과 같고 주체·시각·폐기 여부가 보존된다
    assert stored == session
    assert stored is not None
    assert stored.principal.user_id == session.principal.user_id
    assert stored.expires_at == session.expires_at
    assert stored.created_at == session.created_at
    assert stored.revoked_at is None


async def test_unknown_hash_returns_none(repository: SessionRepository) -> None:
    """없는 토큰 해시는 None이다."""
    # when: 없는 해시로 조회한다
    result = await repository.get_by_token_hash("nope")
    # then: None이다
    assert result is None


async def test_duplicate_hash_is_rejected(repository: SessionRepository) -> None:
    """같은 토큰 해시를 두 번 저장할 수 없다."""
    # given: 해시가 저장된 세션
    await repository.add(make_session(), "same")

    # when·then: 같은 해시로 다시 저장하면 이미 있음 오류다
    with pytest.raises(AlreadyExistsError):
        await repository.add(make_session(), "same")


async def test_update_persists_revocation(repository: SessionRepository) -> None:
    """update는 폐기 상태를 저장한다."""
    # given: 저장된 세션
    session = make_session()
    await repository.add(session, "hash-1")
    # when: 세션을 폐기하고 update한다
    session.revoke(later(30))

    await repository.update(session)

    # then: 조회한 세션에 폐기 시각이 있다
    stored = await repository.get_by_token_hash("hash-1")
    assert stored is not None
    assert stored.revoked_at == later(30)


async def test_update_unknown_session_raises_not_found(repository: SessionRepository) -> None:
    """저장되지 않은 세션을 update하면 찾을 수 없다."""
    # when·then: 없는 세션을 update하면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.update(make_session())


async def test_delete_all_for_user_removes_only_that_users_sessions(
    repository: SessionRepository,
) -> None:
    """사용자의 세션 전체를 지우되 다른 사용자의 세션은 남긴다."""
    # given: kim의 세션 셋(폐기된 것 포함)과 lee의 세션
    await repository.add(make_session(principal=principal_of("kim")), "kim-1")
    await repository.add(make_session(principal=principal_of("kim")), "kim-2")
    already = make_session(principal=principal_of("kim"))
    already.revoke(later(5))
    await repository.add(already, "kim-old")
    await repository.add(make_session(principal=principal_of("lee")), "lee-1")

    # when: kim의 세션을 모두 지운다
    deleted = await repository.delete_all_for_user(uid("kim"))

    # then: 3건이 지워지고 kim의 세션은 없으며 lee의 세션은 남는다
    assert deleted == 3  # 이미 폐기된 세션 행도 지운다(행이 남으면 사용자 물리 삭제를 막는다)
    for token in ("kim-1", "kim-2", "kim-old"):
        assert await repository.get_by_token_hash(token) is None
    assert await repository.get_by_token_hash("lee-1") is not None


async def test_delete_all_for_user_without_sessions_returns_zero(
    repository: SessionRepository,
) -> None:
    """세션이 없는 사용자에서는 0건이 지워진다."""
    # when: 없는 사용자와 세션 없는 사용자를 지운다
    result = await repository.delete_all_for_user(UserId(new_id()))
    # then: 모두 0이다
    assert result == 0
    assert await repository.delete_all_for_user(uid("lee")) == 0


async def test_deleted_sessions_cannot_be_updated_or_revived(
    repository: SessionRepository,
) -> None:
    """지워진 세션은 update하거나 되살릴 수 없다."""
    # given: 저장 뒤 사용자 세션 전체가 삭제된 상태
    session = make_session(principal=principal_of("kim"))
    await repository.add(session, "kim-1")
    await repository.delete_all_for_user(uid("kim"))

    # when·then: 지워진 세션을 update하면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.update(session)
    # then: 해시 조회도 None이다
    assert await repository.get_by_token_hash("kim-1") is None


async def test_delete_others_for_user_keeps_given_token(repository: SessionRepository) -> None:
    """지정한 토큰만 남기고 사용자의 나머지 세션을 지운다."""
    # given: kim의 세션 셋(폐기된 것 포함)과 lee의 세션
    await repository.add(make_session(principal=principal_of("kim")), "kim-keep")
    await repository.add(make_session(principal=principal_of("kim")), "kim-2")
    already = make_session(principal=principal_of("kim"))
    already.revoke(later(5))
    await repository.add(already, "kim-old")
    await repository.add(make_session(principal=principal_of("lee")), "lee-1")

    # when: kim-keep만 남기고 나머지를 지운다
    deleted = await repository.delete_others_for_user(uid("kim"), "kim-keep")

    # then: 2건이 지워지고 kim-keep과 lee의 세션만 남는다
    assert deleted == 2  # 폐기된 행도 지운다
    assert await repository.get_by_token_hash("kim-keep") is not None
    assert await repository.get_by_token_hash("kim-2") is None
    assert await repository.get_by_token_hash("kim-old") is None
    assert await repository.get_by_token_hash("lee-1") is not None  # 다른 사용자는 그대로


async def test_delete_others_for_user_with_only_the_kept_session_returns_zero(
    repository: SessionRepository,
) -> None:
    """남길 세션뿐이면 0건이 지워진다."""
    # given: kim의 세션 하나
    await repository.add(make_session(principal=principal_of("kim")), "kim-keep")

    # when: 그 세션만 남기고 지운다
    result = await repository.delete_others_for_user(uid("kim"), "kim-keep")
    # then: 0건이다
    assert result == 0
    # then: 세션은 남아 있다
    assert await repository.get_by_token_hash("kim-keep") is not None


async def test_delete_others_for_user_does_not_keep_another_users_token_hash(
    repository: SessionRepository,
) -> None:
    """남길 토큰이 다른 사용자의 것이어도 요청한 사용자의 세션은 모두 지워진다."""
    # given: kim과 lee의 세션
    await repository.add(make_session(principal=principal_of("kim")), "kim-1")
    await repository.add(make_session(principal=principal_of("lee")), "lee-1")

    # when: lee의 토큰을 남길 토큰으로 주고 kim의 나머지를 지운다
    deleted = await repository.delete_others_for_user(uid("kim"), "lee-1")

    # then: kim의 세션 1건이 지워지고 lee의 세션은 남는다
    assert deleted == 1
    assert await repository.get_by_token_hash("kim-1") is None
    assert await repository.get_by_token_hash("lee-1") is not None


async def test_delete_others_for_user_without_sessions_returns_zero(
    repository: SessionRepository,
) -> None:
    """세션이 없는 사용자에서는 0건이 지워진다."""
    # when: 세션 없는 사용자에서 지운다
    result = await repository.delete_others_for_user(uid("lee"), "none")
    # then: 0건이다
    assert result == 0
