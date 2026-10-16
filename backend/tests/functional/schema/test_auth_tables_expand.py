"""Feature: 운영자는 인증 테이블을 expand로 올려도 기존 데이터·이전 릴리스 SQL이 유지된다(MIG-1~4).

내리면 새 객체만 사라지고, 다시 올리면 돌아온다.

When: 운영자 명령(alembic upgrade/downgrade).
운영자에게 공개된 인터페이스는 HTTP가 아니라 이 명령이다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    given_schema_at,
    table_names,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.revisions import AUTH_REVISION, OWNER_REVISION
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

PREVIOUS_REVISION = OWNER_REVISION  # 과거 리비전 검증: head가 아니라 AUTH_REVISION까지만 올린다
NEW_TABLES = {"users", "login_failures", "directory_settings"}
OLD_RELEASE_SESSION_INSERT = (
    "insert into auth_sessions (id, token_hash, subject, email, name, role, created_at,"
    " expires_at) values (gen_random_uuid(), '{marker}', 'S-1', null, 'n', '{role}', now(),"
    " now() + interval '1 hour')"
)
SESSION_COLUMNS_SQL = (
    "select string_agg(column_name || ':' || is_nullable, ',' order by column_name)"
    " from information_schema.columns where table_name = 'auth_sessions'"
)
SESSION_INDEX_SQL = "select count(*) from pg_indexes where indexname = 'ix_auth_sessions_subject'"


async def _scalar(url: URL, sql: str) -> object:
    return (await run_sql(url, sql))[0][0]


async def _given_previous_release_with_data(url: URL, marker: str) -> None:
    await given_schema_at(url, PREVIOUS_REVISION)
    await run_sql(
        url,
        "insert into customers (id, company_name, contact_name, notes, created_at,"
        " updated_at) values (gen_random_uuid(), '기존 고객', '담당', '', now(), now())",
    )
    await run_sql(url, OLD_RELEASE_SESSION_INSERT.format(marker=marker, role="sales"))


async def test_operator_upgrade_adds_auth_tables_and_keeps_existing_data(
    blank_database: URL,
) -> None:
    """Scenario: 인증 리비전을 올리면 새 테이블이 생기고 기존 고객·세션 데이터는 그대로다."""
    # Given
    await _given_previous_release_with_data(blank_database, "old-1")
    assert not (NEW_TABLES & await table_names(blank_database))
    columns_before = await _scalar(blank_database, SESSION_COLUMNS_SQL)
    # When
    await when_operator_upgrades(blank_database, target=AUTH_REVISION)
    # Then
    assert await table_names(blank_database) >= NEW_TABLES
    assert await _scalar(blank_database, "select count(*) from customers") == 1
    assert await _scalar(blank_database, "select count(*) from auth_sessions") == 1
    assert await _scalar(blank_database, "select count(*) from users") == 0
    assert await _scalar(blank_database, "select count(*) from directory_settings") == 0
    assert await _scalar(blank_database, SESSION_COLUMNS_SQL) == columns_before


async def test_operator_upgrade_keeps_the_old_release_session_sql_working(
    blank_database: URL,
) -> None:
    """Scenario: 인증 리비전을 올린 뒤에도 이전 릴리스 코드의 세션 INSERT SQL이 동작한다."""
    # Given
    await _given_previous_release_with_data(blank_database, "old-1")
    # When
    await when_operator_upgrades(blank_database, target=AUTH_REVISION)
    # Then
    await run_sql(blank_database, OLD_RELEASE_SESSION_INSERT.format(marker="old-2", role="admin"))
    assert await _scalar(blank_database, "select count(*) from auth_sessions") == 2


async def test_operator_downgrade_removes_only_the_new_objects(blank_database: URL) -> None:
    """Scenario: 인증 리비전을 내리면 새 테이블·인덱스만 사라지고 기존 테이블과 세션 행은 남는다."""
    # Given
    await given_schema_at(blank_database, AUTH_REVISION)
    await run_sql(blank_database, OLD_RELEASE_SESSION_INSERT.format(marker="keep", role="sales"))
    assert await _scalar(blank_database, SESSION_INDEX_SQL) == 1
    # When
    await when_operator_downgrades(blank_database, target=PREVIOUS_REVISION)
    # Then
    tables = await table_names(blank_database)
    assert not (NEW_TABLES & tables)
    assert {"customers", "deals", "auth_sessions"} <= tables
    assert await _scalar(blank_database, SESSION_INDEX_SQL) == 0
    assert await _scalar(blank_database, "select count(*) from auth_sessions") == 1


async def test_operator_upgrade_after_downgrade_restores_the_new_objects(
    blank_database: URL,
) -> None:
    """Scenario: 내렸던 인증 리비전을 다시 올리면 새 테이블·인덱스가 돌아오고 세션 행은 유지된다."""
    # Given
    await given_schema_at(blank_database, AUTH_REVISION)
    await run_sql(blank_database, OLD_RELEASE_SESSION_INSERT.format(marker="keep", role="sales"))
    await when_operator_downgrades(blank_database, target=PREVIOUS_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=AUTH_REVISION)
    # Then
    assert await table_names(blank_database) >= NEW_TABLES
    assert await _scalar(blank_database, SESSION_INDEX_SQL) == 1
    assert await _scalar(blank_database, "select count(*) from auth_sessions") == 1
