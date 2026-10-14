"""UserRepository.has_links / delete / lock_assignable 계약(AC3·6): Fake와 SQL 구현에 같은 기대값.

users를 FK로 참조하는 모든 종류(tests.support.user_links.LINK_KINDS)를 각각 단독으로 만들어
연결 판정이 true가 되는지 확인한다. 세션과 자기 자신이 등록자인 자기참조는 연결이 아니다.
"""

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.session import AuthSession, SessionId
from app.domain.user.errors import UserInUseError
from app.domain.user.value_objects import UserId
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW
from tests.factories_auth import make_resigned_user, make_user
from tests.fakes.unit_of_work import FakeUnitOfWork
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
            await connection.execute(
                text("truncate users, directory_settings, auth_sessions, customers cascade")
            )
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
    target = make_user("kim")
    await _add(uow_factory, target)
    assert not await _has_links(uow_factory, target)

    await link_user(uow_factory, target, kind)

    assert await _has_links(uow_factory, target)


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_a_reference_to_someone_else_does_not_link_this_user(
    uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    target, other = make_user("kim"), make_user("lee")
    await _add(uow_factory, target)
    await _add(uow_factory, other)

    await link_user(uow_factory, other, kind)

    assert not await _has_links(uow_factory, target)


async def test_a_self_registered_user_is_not_linked(uow_factory: UnitOfWorkFactory) -> None:
    user = make_user("kim")  # created_by_user_id == id
    await _add(uow_factory, user)

    assert not await _has_links(uow_factory, user)


async def test_a_session_row_is_not_a_link(uow_factory: UnitOfWorkFactory) -> None:
    user = make_user("kim")
    await _add(uow_factory, user)
    session = AuthSession(
        id=SessionId(uuid4()),
        principal=user.to_principal(),
        created_at=NOW,
        expires_at=NOW + timedelta(hours=8),
    )
    async with uow_factory() as uow:
        await uow.sessions.add(session, "tok")
        await uow.commit()

    assert not await _has_links(uow_factory, user)


async def test_a_resigned_user_with_references_stays_linked(
    uow_factory: UnitOfWorkFactory,
) -> None:
    user = make_user("kim")
    await _add(uow_factory, user)
    await link_user(uow_factory, user, "deal_owner")
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
        stored.resign(NOW)
        await uow.users.update(stored)
        await uow.commit()

    assert await _has_links(uow_factory, user)


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_physical_delete_of_a_linked_user_raises_user_in_use_and_keeps_the_row(
    uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    target = make_user("kim")
    await _add(uow_factory, target)
    await link_user(uow_factory, target, kind)

    async with uow_factory() as uow:
        with pytest.raises(UserInUseError):
            await uow.users.delete(target.id)

    async with uow_factory() as uow:
        assert (await uow.users.get(target.id)).id == target.id


async def test_physical_delete_of_an_unlinked_user_succeeds(
    uow_factory: UnitOfWorkFactory,
) -> None:
    target = make_user("kim")
    await _add(uow_factory, target)

    async with uow_factory() as uow:
        await uow.users.delete(target.id)
        await uow.commit()

    assert not await _exists(uow_factory, target.id)


async def _exists(uow_factory: UnitOfWorkFactory, user_id: UserId) -> bool:
    async with uow_factory() as uow:
        return bool(await uow.users.get_refs([user_id]))


async def test_lock_assignable_is_true_only_for_an_active_user(
    uow_factory: UnitOfWorkFactory,
) -> None:
    active, gone = make_user("kim"), make_resigned_user("gone")
    await _add(uow_factory, active)
    await _add(uow_factory, gone)

    async with uow_factory() as uow:
        assert await uow.users.lock_assignable(active.id) is True
        assert await uow.users.lock_assignable(gone.id) is False
        assert await uow.users.lock_assignable(UserId(uuid4())) is False
