from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.fakes.unit_of_work import FixedClock
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack


@pytest_asyncio.fixture
async def session(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    async with rolled_back_session(test_database_url) as active:
        yield active


@dataclass(frozen=True, slots=True)
class RealAuth:
    """실제 PostgreSQL UoW + FakeDirectoryAuthenticator로 조립한 인증 유스케이스."""

    uow_factory: UnitOfWorkFactory
    stack: AuthStack
    directory: FakeDirectoryAuthenticator


@pytest_asyncio.fixture
async def real_auth(test_database_url: URL) -> AsyncIterator[RealAuth]:
    from tests.fakes.auth_stack import build_auth_stack  # noqa: PLC0415 - 지연 import

    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        uow_factory = sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        directory = FakeDirectoryAuthenticator()
        directory.add_account("kim", "pw-kim")
        directory.add_account("lee", "pw-lee")
        yield RealAuth(
            uow_factory, build_auth_stack(uow_factory, FixedClock(NOW), directory), directory
        )
        async with engine.begin() as connection:
            await connection.execute(
                text("truncate users, login_failures, directory_settings, auth_sessions cascade")
            )
    finally:
        await engine.dispose()
