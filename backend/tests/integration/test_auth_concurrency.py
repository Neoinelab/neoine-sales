"""실제 PostgreSQL 동시성(저장소 수준): 명단 advisory lock, 활성 login_id 유일, AD 설정 낙관적 잠금.

(DS-7, USER-3). 최초 admin 등록·상호 삭제 경쟁은 제품 유스케이스를 호출하는
test_user_roster_lock.py와 test_user_delete_race.py가 검증한다(여기에 로직을 다시 구현하지 않는다).
"""

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError
from app.domain.directory.errors import DirectorySettingsConflictError
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW, later
from tests.factories_auth import make_directory_settings, make_user

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.unit_of_work import UnitOfWorkFactory

pytestmark = pytest.mark.integration
WAIT = 0.5


@pytest_asyncio.fixture
async def uow_factory(test_database_url: URL) -> AsyncIterator[UnitOfWorkFactory]:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await connection.execute(
                text("truncate users, login_failures, directory_settings, auth_sessions cascade")
            )
    finally:
        await engine.dispose()


async def _active_admins(uow_factory: UnitOfWorkFactory) -> int:
    async with uow_factory() as uow:
        return await uow.users.count_active_admins()


async def test_second_roster_lock_waits_until_the_first_unit_finishes(
    uow_factory: UnitOfWorkFactory,
) -> None:
    async def second() -> None:
        async with uow_factory() as uow:
            await uow.users.lock_roster()

    async with uow_factory() as first:
        await first.users.lock_roster()
        waiter = asyncio.create_task(second())
        await asyncio.sleep(WAIT)
        assert not waiter.done(), "첫 단위가 명단 잠금을 쥐고 있는 동안 두 번째가 진행되면 안 된다"

    await asyncio.wait_for(waiter, timeout=10)


async def test_concurrent_registration_of_the_same_login_id_lets_only_one_win(
    uow_factory: UnitOfWorkFactory,
) -> None:
    async def register(role: Role) -> str:
        async with uow_factory() as uow:
            try:
                await uow.users.add(make_user("kim", role))
                await asyncio.sleep(WAIT)
                await uow.commit()
            except AlreadyExistsError:
                return "duplicate"
            return "created"

    results = await asyncio.gather(register(Role.SALES), register(Role.USER))

    assert sorted(results) == ["created", "duplicate"]
    async with uow_factory() as check:
        users = await check.users.list_active()
    assert [u.login_id for u in users] == [LoginId("kim")]


async def test_concurrent_first_settings_save_lets_only_one_win(
    uow_factory: UnitOfWorkFactory,
) -> None:
    first = uow_factory()
    await first.__aenter__()
    try:
        await first.directory_settings.save(
            make_directory_settings(base_dn="dc=first"),
            expected_revision=None,
            updated_by=None,
            now=NOW,
        )

        async def second() -> None:
            async with uow_factory() as uow:
                await uow.directory_settings.save(
                    make_directory_settings(base_dn="dc=second"),
                    expected_revision=None,
                    updated_by=None,
                    now=later(1),
                )
                await uow.commit()

        waiter = asyncio.create_task(second())
        await asyncio.sleep(WAIT)
        assert not waiter.done(), "같은 기본키 생성은 첫 트랜잭션이 끝날 때까지 기다려야 한다"
        await first.commit()
        with pytest.raises(DirectorySettingsConflictError):
            await asyncio.wait_for(waiter, timeout=10)
    finally:
        await first.__aexit__(None, None, None)

    async with uow_factory() as check:
        stored = await check.directory_settings.get()
    assert stored is not None
    assert (stored.revision, stored.settings.base_dn) == (1, "dc=first")


async def test_concurrent_settings_update_with_same_revision_lets_only_one_win(
    uow_factory: UnitOfWorkFactory,
) -> None:
    async with uow_factory() as seed:
        await seed.directory_settings.save(
            make_directory_settings(), expected_revision=None, updated_by=None, now=NOW
        )
        await seed.commit()

    async def update(by: str, base_dn: str, at: int) -> str:
        async with uow_factory() as uow:
            try:
                await uow.directory_settings.save(
                    make_directory_settings(base_dn=base_dn),
                    expected_revision=1,
                    updated_by=by,
                    now=later(at),
                )
                await asyncio.sleep(WAIT)
                await uow.commit()
            except DirectorySettingsConflictError:
                return "conflict"
            return "saved"

    results = await asyncio.gather(update("a", "dc=a", 1), update("b", "dc=b", 2))

    assert sorted(results) == ["conflict", "saved"]
    async with uow_factory() as check:
        stored = await check.directory_settings.get()
    assert stored is not None
    assert stored.revision == 2
    assert stored.updated_by in {"a", "b"}
    assert stored.settings.base_dn == f"dc={stored.updated_by}"
