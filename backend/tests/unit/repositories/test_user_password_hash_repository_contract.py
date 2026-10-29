"""UserPasswordHashRepository 계약(AC13): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

사용자 id 하나에 해시 행 하나(upsert). 사용자가 없으면 UserNotFoundError(FK 위반을 변환).
사용자를 물리 삭제하면 해시도 함께 사라지고(ON DELETE CASCADE), 해시는 삭제를 막는 연결이 아니다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from app.domain.auth.password_hash import PasswordHash
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.user.errors import UserNotFoundError
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW, later
from tests.factories_auth import make_user
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.ids import new_id
from tests.support.truncate import truncate_business_tables

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
FIRST = PasswordHash(
    "scrypt$ln=14,r=8,p=1$c2FsdC0xc2FsdC0xc2FsdA$aGFzaC0xaGFzaC0xaGFzaC0xaGFzaC0xaGFzaC0x"
)
SECOND = PasswordHash(
    "scrypt$ln=14,r=8,p=1$c2FsdC0yc2FsdC0yc2FsdA$aGFzaC0yaGFzaC0yaGFzaC0yaGFzaC0yaGFzaC0y"
)


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


async def _user(uow_factory: UnitOfWorkFactory, login_id: str = "kim") -> User:
    user = make_user(login_id)
    async with uow_factory() as uow:
        await uow.users.add(user)
        await uow.commit()
    return user


async def _save(
    uow_factory: UnitOfWorkFactory, user: User, value: PasswordHash, at: datetime = NOW
) -> None:
    async with uow_factory() as uow:
        await uow.password_hashes.save(user.id, value, at)
        await uow.commit()


async def _get(uow_factory: UnitOfWorkFactory, user: User) -> PasswordHash | None:
    async with uow_factory() as uow:
        return await uow.password_hashes.get(user.id)


async def test_save_then_get_round_trips(uow_factory: UnitOfWorkFactory) -> None:
    user = await _user(uow_factory)

    await _save(uow_factory, user, FIRST)

    assert await _get(uow_factory, user) == FIRST


async def test_save_overwrites_existing_hash(uow_factory: UnitOfWorkFactory) -> None:
    user = await _user(uow_factory)
    await _save(uow_factory, user, FIRST)

    await _save(uow_factory, user, SECOND, later(60))

    assert await _get(uow_factory, user) == SECOND


async def test_get_missing_returns_none(uow_factory: UnitOfWorkFactory) -> None:
    user = await _user(uow_factory)

    assert await _get(uow_factory, user) is None


async def test_hashes_are_kept_per_user(uow_factory: UnitOfWorkFactory) -> None:
    kim = await _user(uow_factory, "kim")
    lee = await _user(uow_factory, "lee")
    await _save(uow_factory, kim, FIRST)

    assert await _get(uow_factory, lee) is None
    await _save(uow_factory, lee, SECOND)

    assert await _get(uow_factory, kim) == FIRST
    assert await _get(uow_factory, lee) == SECOND


async def test_delete_removes_only_that_users_hash(uow_factory: UnitOfWorkFactory) -> None:
    kim = await _user(uow_factory, "kim")
    lee = await _user(uow_factory, "lee")
    await _save(uow_factory, kim, FIRST)
    await _save(uow_factory, lee, SECOND)

    async with uow_factory() as uow:
        await uow.password_hashes.delete(kim.id)
        await uow.commit()

    assert await _get(uow_factory, kim) is None
    assert await _get(uow_factory, lee) == SECOND


async def test_delete_missing_is_not_error(uow_factory: UnitOfWorkFactory) -> None:
    user = await _user(uow_factory)

    async with uow_factory() as uow:
        await uow.password_hashes.delete(user.id)  # 예외가 없으면 통과
        await uow.commit()

    assert await _get(uow_factory, user) is None


async def test_save_for_missing_user_raises_user_not_found(uow_factory: UnitOfWorkFactory) -> None:
    async with uow_factory() as uow:
        with pytest.raises(UserNotFoundError):
            await uow.password_hashes.save(new_id(), FIRST, NOW)  # type: ignore[arg-type]


async def test_uncommitted_save_is_discarded(uow_factory: UnitOfWorkFactory) -> None:
    user = await _user(uow_factory)

    async with uow_factory() as uow:
        await uow.password_hashes.save(user.id, FIRST, NOW)

    assert await _get(uow_factory, user) is None


async def test_password_hash_does_not_count_as_link(uow_factory: UnitOfWorkFactory) -> None:
    user = await _user(uow_factory)
    await _save(uow_factory, user, FIRST)

    async with uow_factory() as uow:
        assert await uow.users.has_links(user.id) is False


async def test_physical_delete_cascades_password_hash(uow_factory: UnitOfWorkFactory) -> None:
    user = await _user(uow_factory)
    await _save(uow_factory, user, FIRST)

    async with uow_factory() as uow:
        await uow.users.delete(user.id)  # 해시가 있어도 막히지 않는다
        await uow.commit()

    assert await _get(uow_factory, user) is None
