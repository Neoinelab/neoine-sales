from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.fakes.unit_of_work import FixedClock
from tests.support.database import (
    apply_migrations,
    create_database,
    drop_database,
    resolve_admin_url,
    rolled_back_session,
    run_async,
    temporary_database,
)
from tests.support.revisions import LEGACY_HEAD
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack


@pytest_asyncio.fixture
async def session(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    async with rolled_back_session(test_database_url) as active:
        yield active


@pytest.fixture(scope="session")
def database_at() -> Iterator[Callable[[str], URL]]:
    """리비전별 임시 DB를 (처음 요청할 때) 만들어 돌려주는 팩토리. 과거 리비전 테스트용.

    head 대신 target을 고정하므로 이후 리비전이 생겨도 과거 스키마를 전제한 테스트가 깨지지 않는다.
    `test_database_url`을 모듈 안에서 이 팩토리의 결과로 덮어쓰면 `session` fixture도 따라온다.
    (덮어쓴 fixture와 순환하지 않도록 이 fixture는 test_database_url에 의존하지 않는다.)
    """
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 과거 리비전 통합 테스트를 건너뜁니다")
    created: dict[str, URL] = {}

    def get(revision: str) -> URL:
        if revision not in created:
            url = run_async(create_database(admin_url))
            run_async(apply_migrations(url, target=revision))
            created[revision] = url
        return created[revision]

    yield get
    for url in created.values():
        run_async(drop_database(admin_url, url.database or ""))


@pytest_asyncio.fixture
async def legacy_db() -> AsyncIterator[URL]:
    """LEGACY_HEAD(사용자 FK 이전)까지만 적용된 빈 임시 DB. 마이그레이션 변환 테스트용."""
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 테스트를 건너뜁니다")
    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=LEGACY_HEAD)
        yield url


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
