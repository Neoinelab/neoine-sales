"""마이그레이션 expand 호환·왕복(MIG-1~4): 이전 릴리스 SQL과 downgrade/upgrade."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.database import apply_migrations, resolve_admin_url, temporary_database
from tests.support.revisions import AUTH_REVISION, OWNER_REVISION
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

PREVIOUS_REVISION = OWNER_REVISION  # 과거 리비전 검증: head가 아니라 AUTH_REVISION까지만 올린다
NEW_TABLES = {"users", "login_failures", "directory_settings"}


async def _table_names(url: URL) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()


async def _scalar(url: URL, sql: str) -> object:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            return (await connection.execute(text(sql))).scalar()
    finally:
        await engine.dispose()


async def _execute(url: URL, sql: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(sql))
    finally:
        await engine.dispose()


OLD_RELEASE_SESSION_INSERT = (
    "insert into auth_sessions (id, token_hash, subject, email, name, role, created_at,"
    " expires_at) values (gen_random_uuid(), '{marker}', 'S-1', null, 'n', '{role}', now(),"
    " now() + interval '1 hour')"
)


async def test_upgrade_keeps_existing_data_and_old_release_sql_still_works() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 expand 호환 테스트를 건너뜁니다")

    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=PREVIOUS_REVISION)
        assert not (NEW_TABLES & await _table_names(url))
        await _execute(
            url,
            "insert into customers (id, company_name, contact_name, notes, created_at,"
            " updated_at) values (gen_random_uuid(), '기존 고객', '담당', '', now(), now())",
        )
        await _execute(url, OLD_RELEASE_SESSION_INSERT.format(marker="old-1", role="sales"))
        columns_before = await _scalar(
            url,
            "select string_agg(column_name || ':' || is_nullable, ',' order by column_name)"
            " from information_schema.columns where table_name = 'auth_sessions'",
        )

        await apply_migrations(url, target=AUTH_REVISION)

        assert await _table_names(url) >= NEW_TABLES
        assert await _scalar(url, "select count(*) from customers") == 1
        assert await _scalar(url, "select count(*) from auth_sessions") == 1
        assert await _scalar(url, "select count(*) from users") == 0
        assert await _scalar(url, "select count(*) from directory_settings") == 0
        columns_after = await _scalar(
            url,
            "select string_agg(column_name || ':' || is_nullable, ',' order by column_name)"
            " from information_schema.columns where table_name = 'auth_sessions'",
        )
        assert columns_after == columns_before
        await _execute(url, OLD_RELEASE_SESSION_INSERT.format(marker="old-2", role="admin"))
        assert await _scalar(url, "select count(*) from auth_sessions") == 2


async def test_downgrade_removes_only_the_new_objects_and_upgrade_restores_them() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 왕복 테스트를 건너뜁니다")

    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=AUTH_REVISION)
        await _execute(url, OLD_RELEASE_SESSION_INSERT.format(marker="keep", role="sales"))
        index_sql = "select count(*) from pg_indexes where indexname = 'ix_auth_sessions_subject'"
        assert await _scalar(url, index_sql) == 1

        await apply_migrations(url, direction="down", target=PREVIOUS_REVISION)

        tables = await _table_names(url)
        assert not (NEW_TABLES & tables)
        assert {"customers", "deals", "auth_sessions"} <= tables
        assert await _scalar(url, index_sql) == 0
        assert await _scalar(url, "select count(*) from auth_sessions") == 1

        await apply_migrations(url, target=AUTH_REVISION)

        assert await _table_names(url) >= NEW_TABLES
        assert await _scalar(url, index_sql) == 1
        assert await _scalar(url, "select count(*) from auth_sessions") == 1
