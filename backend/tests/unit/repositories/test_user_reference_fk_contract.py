"""사용자 참조 FK 위반의 도메인 오류 계약: Fake와 SQL(실제 PostgreSQL) 공통.

선택한 계약(infra 구현자가 따른다):
- SessionRepository.add: 세션 소유 user_id 행이 없으면(로그인 직후 물리 삭제된 경쟁) 원시
  IntegrityError나 AuthenticationError가 아니라 `UserNotFoundError`(도메인)를 던진다.
- UserRepository.add: created_by_user_id가 가리키는 행이 없으면(요청 admin이 그 사이 물리 삭제된
  경쟁) `UserNotFoundError`를 던진다. 자기 자신을 가리키는 행(최초 admin)은 허용한다.
두 경우 모두 SAVEPOINT 안에서 변환하므로 바깥 트랜잭션은 계속 쓸 수 있어야 한다.
"""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.auth.session import AuthSession, SessionId
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId
from app.infra.db.session_repository import SqlSessionRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW
from tests.factories_auth import make_principal, make_user
from tests.fakes.session_repository import FakeSessionRepository
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session
from tests.support.ids import new_id

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.session_repository import SessionRepository
    from app.application.ports.user_repository import UserRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


def _session_of(user_id: UserId) -> AuthSession:
    return AuthSession(
        id=SessionId(new_id()),
        principal=make_principal("kim", user_id=user_id),
        created_at=NOW,
        expires_at=NOW + timedelta(hours=8),
    )


@pytest_asyncio.fixture(params=PARAMS)
async def pair(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[UserRepository, SessionRepository]]:
    """같은 저장소(트랜잭션)를 공유하는 (사용자 저장소, 세션 저장소) 쌍."""
    if request.param == "fake":
        users = FakeUserRepository()
        users.enforce_creator_fk = True
        yield users, FakeSessionRepository(user_exists=lambda user_id: user_id in users._items)
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlUserRepository(session), SqlSessionRepository(session)


async def test_session_add_for_a_missing_user_raises_user_not_found(
    pair: tuple[UserRepository, SessionRepository],
) -> None:
    """없는 사용자의 세션을 추가하면 UserNotFoundError가 난다."""
    # given: 세션 저장소 (전제: 사용자가 하나도 없다)
    _, sessions = pair

    # when·then: 없는 사용자의 세션을 추가하면 UserNotFoundError가 난다
    with pytest.raises(UserNotFoundError):
        await sessions.add(_session_of(UserId(new_id())), "hash-1")


async def test_session_add_for_a_missing_user_stores_nothing_and_keeps_the_transaction_usable(
    pair: tuple[UserRepository, SessionRepository],
) -> None:
    """없는 사용자의 세션 추가가 실패해도 아무것도 저장되지 않고 트랜잭션은 계속 쓸 수 있다."""
    # given: 사용자 한 명이 있다
    users, sessions = pair
    kim = make_user("kim")
    await users.add(kim)

    # when: 없는 사용자의 세션 추가가 실패한 뒤 같은 트랜잭션에서 있는 사용자의 세션을 추가한다
    with pytest.raises(UserNotFoundError):
        await sessions.add(_session_of(UserId(new_id())), "ghost")
    await sessions.add(_session_of(kim.id), "real")  # 같은 트랜잭션에서 계속 쓸 수 있다

    # then: 실패한 세션은 없고 성공한 세션은 있다
    assert await sessions.get_by_token_hash("ghost") is None
    assert await sessions.get_by_token_hash("real") is not None


async def test_user_add_with_a_missing_creator_raises_user_not_found(
    pair: tuple[UserRepository, SessionRepository],
) -> None:
    """없는 등록자를 가리키는 사용자를 추가하면 UserNotFoundError가 난다."""
    # given: 없는 사용자를 등록자로 가진 사용자
    users, _ = pair
    orphan = make_user("kim", created_by_user_id=UserId(new_id()))

    # when·then: 추가하면 UserNotFoundError가 난다
    with pytest.raises(UserNotFoundError):
        await users.add(orphan)

    # then: 저장되지 않았다
    assert await users.get_active_by_login_id(orphan.login_id) is None


async def test_user_add_with_a_missing_creator_keeps_the_transaction_usable(
    pair: tuple[UserRepository, SessionRepository],
) -> None:
    """등록자 누락으로 추가가 실패해도 트랜잭션은 계속 쓸 수 있다."""
    # given: 등록자가 없는 사용자 추가가 실패했다
    users, _ = pair
    with pytest.raises(UserNotFoundError):
        await users.add(make_user("kim", created_by_user_id=UserId(new_id())))

    # when: 같은 트랜잭션에서 다른 사용자를 추가한다
    boss = make_user("boss")
    await users.add(boss)  # 같은 트랜잭션에서 계속 쓸 수 있다

    # then: 추가한 사용자를 읽을 수 있다
    assert (await users.get(boss.id)).login_id == boss.login_id


async def test_user_add_that_points_at_itself_is_allowed(
    pair: tuple[UserRepository, SessionRepository],
) -> None:
    """자기 자신을 등록자로 가리키는 사용자(최초 admin)는 추가할 수 있다."""
    # given: 등록자가 자기 자신인 최초 admin
    users, _ = pair
    first = make_user("root")  # 최초 admin: created_by_user_id == id

    # when: 추가한다
    await users.add(first)

    # then: 등록자가 자기 자신으로 저장된다
    assert (await users.get(first.id)).created_by_user_id == first.id
