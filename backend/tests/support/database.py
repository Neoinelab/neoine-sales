"""통합 테스트용 임시 PostgreSQL DB 생성·삭제, 마이그레이션 적용, 롤백되는 세션 도우미.

개발 DB의 데이터에는 접속하지 않는다. 관리자 접속(maintenance DB)으로 `app_test_*` DB를 만들고
그 안에서만 테스트한 뒤 지운다.
"""

import argparse
import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.config import Profile, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine, Sequence

BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_async[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """동기 fixture에서 코루틴을 실행한다. 루프가 이미 돌고 있어도 안전하도록 스레드를 쓴다."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def resolve_admin_url() -> URL | None:
    """임시 DB를 만들 관리자 접속 URL. CI는 환경변수로, 로컬은 앱 설정에서 유도한다.

    환경변수 TEST_DATABASE_ADMIN_URL이 없으면 local 프로파일일 때만 앱 설정의 접속 정보를
    maintenance DB(postgres)로 바꿔 쓴다. 그 외에는 None(통합 테스트 건너뜀).
    """
    explicit = os.environ.get("TEST_DATABASE_ADMIN_URL")
    if explicit:
        return make_url(explicit)
    try:
        settings = get_settings()
    except ValueError:
        return None
    if settings.profile is not Profile.LOCAL:
        return None
    return make_url(str(settings.database_url)).set(database="postgres")


async def create_database(admin_url: URL) -> URL:
    name = f"app_test_{uuid.uuid4().hex[:8]}"
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            # 이름은 위에서 직접 생성한 값이므로 SQL 주입 위험이 없다.
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()
    return admin_url.set(database=name)


async def drop_database(admin_url: URL, name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _run(
    action: Callable[[Config, str], None], target: str, x_args: Sequence[str] = ()
) -> Callable[[Connection], None]:
    def runner(connection: Connection) -> None:
        config = _alembic_config()
        config.attributes["connection"] = connection
        if x_args:  # `alembic -x key=value`와 같다: env.py의 context.get_x_argument()가 읽는다
            config.cmd_opts = argparse.Namespace(x=list(x_args))
        action(config, target)

    return runner


async def apply_migrations(
    url: URL, *, direction: str = "up", target: str = "head", x_args: Sequence[str] = ()
) -> None:
    """마이그레이션을 한 트랜잭션으로 적용한다. x_args는 `alembic -x` 인자(예: name_map=<경로>)."""
    action = command.upgrade if direction == "up" else command.downgrade
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_run(action, target, x_args))
    finally:
        await engine.dispose()


@asynccontextmanager
async def rolled_back_session(url: URL) -> AsyncIterator[AsyncSession]:
    """바깥 트랜잭션 안에서 동작하고 끝나면 모두 롤백되는 세션(SAVEPOINT 사용)."""
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            session = AsyncSession(
                bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
            )
            try:
                yield session
            finally:
                await session.close()
                await transaction.rollback()
    finally:
        await engine.dispose()


@asynccontextmanager
async def temporary_database(admin_url: URL) -> AsyncIterator[URL]:
    """마이그레이션이 적용되지 않은 빈 임시 DB (마이그레이션 왕복 테스트용)."""
    url = await create_database(admin_url)
    try:
        yield url
    finally:
        await drop_database(admin_url, url.database or "")
