"""UserRepository.has_links / delete / lock_assignable 계약: Fake와 SQL 구현에 같은 기대값.

users를 FK로 참조하는 모든 종류(tests.support.user_links.LINK_KINDS)를 각각 단독으로 만들어
연결 판정이 true가 되는지 확인한다(17종). 세션·비밀번호 해시는 연결이 아니고,
사용자 행끼리는 서로 참조하지 않는다(등록자 없음).
"""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.session import AuthSession, SessionId
from app.domain.user.errors import UserInUseError
from app.domain.user.value_objects import UserId
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW
from tests.factories_auth import make_resigned_user, make_user
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.ids import new_id
from tests.support.truncate import truncate_business_tables
from tests.support.user_links import LINK_KINDS, link_user

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def uow_factory(request: pytest.FixtureRequest) -> AsyncIterator[UnitOfWorkFactory]:
    if request.param == "fake":
        shared = FakeUnitOfWork()
        yield lambda: shared
        return
    url = request.getfixturevalue("test_database_url")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await truncate_business_tables(connection)
    finally:
        await engine.dispose()


async def _add(uow_factory: UnitOfWorkFactory, user: User) -> None:
    async with uow_factory() as uow:
        await uow.users.add(user)
        await uow.commit()


async def _has_links(uow_factory: UnitOfWorkFactory, user: User) -> bool:
    async with uow_factory() as uow:
        return await uow.users.has_links(user.id)


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_each_kind_of_reference_alone_makes_the_user_linked(
    uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    """users를 참조하는 종류 하나만 있어도 사용자는 연결된 것으로 판정된다."""
    # given: 연결이 없는 사용자
    target = make_user("kim")
    await _add(uow_factory, target)
    before = await _has_links(uow_factory, target)

    # when: 해당 종류의 참조를 하나 만든다
    await link_user(uow_factory, target, kind)
    after = await _has_links(uow_factory, target)

    # then: 만들기 전에는 연결이 없고 만든 뒤에는 연결된 것으로 판정된다
    assert not before
    assert after


async def test_other_user_rows_never_make_a_user_linked(uow_factory: UnitOfWorkFactory) -> None:
    """다른 사용자 행이 있어도(다른 사용자를 등록한 admin이어도) 연결로 판정되지 않는다.

    테스트 코드: US-112
    """
    # given: 사용자 셋이 저장되어 있다(users 사이에는 참조 열이 없다)
    boss, kim, lee = make_user("boss"), make_user("kim"), make_user("lee")
    for user in (boss, kim, lee):
        await _add(uow_factory, user)

    # when: 각 사용자의 연결 여부를 본다
    results = [await _has_links(uow_factory, user) for user in (boss, kim, lee)]

    # then: 아무도 연결되지 않았다
    assert results == [False, False, False]


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_a_reference_to_someone_else_does_not_link_this_user(
    uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    """다른 사용자를 향한 참조는 이 사용자를 연결된 것으로 만들지 않는다."""
    # given: 사용자 둘
    target, other = make_user("kim"), make_user("lee")
    await _add(uow_factory, target)
    await _add(uow_factory, other)

    # when: 다른 사용자에게 참조를 만든다
    await link_user(uow_factory, other, kind)

    # then: 이 사용자는 연결되지 않았다
    assert not await _has_links(uow_factory, target)


async def test_a_self_registered_user_is_not_linked(uow_factory: UnitOfWorkFactory) -> None:
    """자기 자신이 등록자인 사용자는 연결된 것이 아니다."""
    # given: 등록자가 자기 자신인 사용자
    user = make_user("kim")  # created_by_user_id == id
    await _add(uow_factory, user)

    # when: 연결 여부를 조회한다
    result = await _has_links(uow_factory, user)
    # then: 연결되지 않은 것으로 판정된다
    assert not result


async def test_a_session_row_is_not_a_link(uow_factory: UnitOfWorkFactory) -> None:
    """세션 행은 연결이 아니다."""
    # given: 세션이 있는 사용자
    user = make_user("kim")
    await _add(uow_factory, user)
    session = AuthSession(
        id=SessionId(new_id()),
        principal=user.to_principal(),
        created_at=NOW,
        expires_at=NOW + timedelta(hours=8),
    )
    async with uow_factory() as uow:
        await uow.sessions.add(session, "tok")
        await uow.commit()

    # when: 연결 여부를 조회한다
    result = await _has_links(uow_factory, user)
    # then: 세션 행은 연결로 치지 않는다
    assert not result


async def test_a_resigned_user_with_references_stays_linked(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """참조가 있는 사용자는 퇴사 처리를 해도 연결된 상태다."""
    # given: 참조가 있는 사용자를 퇴사 처리했다
    user = make_user("kim")
    await _add(uow_factory, user)
    await link_user(uow_factory, user, "deal_owner")
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
        stored.resign(NOW)
        await uow.users.update(stored)
        await uow.commit()

    # when: 연결 여부를 조회한다
    result = await _has_links(uow_factory, user)
    # then: 연결된 것으로 판정된다
    assert result


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_physical_delete_of_a_linked_user_raises_user_in_use_and_keeps_the_row(
    uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    """연결된 사용자의 물리 삭제는 UserInUseError이고 행은 남는다."""
    # given: 해당 종류의 참조가 있는 사용자
    target = make_user("kim")
    await _add(uow_factory, target)
    await link_user(uow_factory, target, kind)

    # when·then: 물리 삭제하면 UserInUseError가 난다
    async with uow_factory() as uow:
        with pytest.raises(UserInUseError):
            await uow.users.delete(target.id)

    # then: 사용자 행은 남아 있다
    async with uow_factory() as uow:
        assert (await uow.users.get(target.id)).id == target.id


async def test_physical_delete_of_an_unlinked_user_succeeds(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """연결이 없는 사용자는 물리 삭제된다."""
    # given: 연결이 없는 사용자
    target = make_user("kim")
    await _add(uow_factory, target)

    # when: 물리 삭제한다
    async with uow_factory() as uow:
        await uow.users.delete(target.id)
        await uow.commit()

    # then: 사용자가 없다
    assert not await _exists(uow_factory, target.id)


async def _exists(uow_factory: UnitOfWorkFactory, user_id: UserId) -> bool:
    async with uow_factory() as uow:
        return bool(await uow.users.get_refs([user_id]))


async def test_lock_assignable_is_true_only_for_an_active_user(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """lock_assignable은 재직 사용자에게만 true다."""
    # given: 재직 사용자와 퇴사 사용자
    active, gone = make_user("kim"), make_resigned_user("gone")
    await _add(uow_factory, active)
    await _add(uow_factory, gone)

    # when·then: 재직자는 true, 퇴사자와 없는 id는 false다
    async with uow_factory() as uow:
        assert await uow.users.lock_assignable(active.id) is True
        assert await uow.users.lock_assignable(gone.id) is False
        assert await uow.users.lock_assignable(UserId(new_id())) is False
