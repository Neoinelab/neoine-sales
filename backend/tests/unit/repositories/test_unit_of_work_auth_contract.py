"""UnitOfWork가 사용자·로그인 실패·AD 설정 저장소를 같은 트랜잭션 규칙으로 다룬다(T-P10)."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.credentials import LoginId
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW, later
from tests.factories_auth import make_counter, make_directory_settings, make_user
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.truncate import truncate_business_tables
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users
from tests.unit.repositories.test_session_repository_contract import make_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.unit_of_work import UnitOfWorkFactory

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


async def _write_everything(uow_factory: UnitOfWorkFactory, *, commit: bool) -> None:
    async with uow_factory() as uow:
        await uow.users.add(make_user("kim"))
        await uow.login_failures.save(make_counter("a" * 64, failures=2))
        await uow.directory_settings.save(
            make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
        )
        if commit:
            await uow.commit()


async def test_committed_auth_changes_are_visible_to_later_units(
    uow_factory: UnitOfWorkFactory,
) -> None:
    await _write_everything(uow_factory, commit=True)

    async with uow_factory() as uow:
        assert await uow.users.get_active_by_login_id(LoginId("kim")) is not None
        counter = await uow.login_failures.get_for_update("a" * 64)
        assert counter is not None
        assert counter.failures == 2
        stored = await uow.directory_settings.get()
        assert stored is not None
        assert stored.revision == 1


async def test_uncommitted_auth_changes_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    await _write_everything(uow_factory, commit=False)

    async with uow_factory() as uow:
        assert await uow.users.get_active_by_login_id(LoginId("kim")) is None
        assert await uow.login_failures.get_for_update("a" * 64) is None
        assert await uow.directory_settings.get() is None
        assert await uow.users.count_active_admins() == 0


async def test_exception_rolls_back_auth_changes(uow_factory: UnitOfWorkFactory) -> None:
    class BoomError(Exception):
        pass

    async def failing_unit() -> None:
        async with uow_factory() as uow:
            await uow.users.add(make_user("kim"))
            raise BoomError

    with pytest.raises(BoomError):
        await failing_unit()

    async with uow_factory() as later_uow:
        assert await later_uow.users.get_active_by_login_id(LoginId("kim")) is None


async def test_changes_after_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    async with uow_factory() as uow:
        user = make_user("kim")
        await uow.users.add(user)
        await uow.commit()
        user.record_login(later(10), display_name="나중", email=None)
        await uow.users.update(user)
        await uow.directory_settings.save(
            make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
        )

    async with uow_factory() as check:
        stored = await check.users.get(user.id)
        assert stored.last_login_at is None
        assert await check.directory_settings.get() is None


async def test_session_deletion_by_user_rolls_back_with_the_unit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    async with uow_factory() as uow:
        await ensure_users(uow.users, uid("kim"))
        await uow.sessions.add(make_session(), "tok")
        await uow.commit()

    async with uow_factory() as uow:
        assert await uow.sessions.delete_all_for_user(uid("kim")) == 1

    async with uow_factory() as check:
        assert await check.sessions.get_by_token_hash("tok") is not None


async def test_resignation_and_session_deletion_commit_together(
    uow_factory: UnitOfWorkFactory,
) -> None:
    async with uow_factory() as uow:
        await ensure_users(uow.users, uid("kim"))
        await uow.sessions.add(make_session(), "tok")
        await uow.commit()

    async with uow_factory() as uow:
        user = await uow.users.get(uid("kim"))
        user.resign(later(5))
        await uow.users.update(user)
        await uow.sessions.delete_all_for_user(uid("kim"))
        await uow.commit()

    async with uow_factory() as check:
        assert not (await check.users.get(uid("kim"))).is_active
        assert await check.sessions.get_by_token_hash("tok") is None
