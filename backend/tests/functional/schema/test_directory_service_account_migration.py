"""Feature: 운영자는 AD 설정 개편 리비전을 올리고 내려 directory_settings를 서비스 계정 구조로 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 파트너 Activity 리비전 다음이고 head다.
올리면 기존 AD 설정 행은 지워지고(데이터 이전 없음, 사용자 결정 D4) `directory_settings`가 새 컬럼
구조가 되며 빈 `user_password_hashes` 테이블이 생긴다. 사용자·세션 등 다른 테이블은 그대로다.
내리면 `user_password_hashes`가 사라지고 설정 행은 비며 구 컬럼 구조로 돌아간다(구 설정 값과 해시는
되살아나지 않는다).
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from tests.functional.steps.schema import (
    column_names,
    given_rows,
    given_schema_at,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.directory_rows import insert_password_hash, insert_settings
from tests.support.head_rows import insert_user
from tests.support.revisions import PARTNER_MEETINGS_REVISION, directory_service_account_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

OLD_COLUMNS = {
    "server_urls",
    "use_starttls",
    "ca_cert_pem",
    "bind_template",
    "display_name_attribute",
    "email_attribute",
    "receive_timeout_seconds",
}
NEW_COLUMNS = {"host", "port", "security", "bind_account", "bind_password_encrypted"}
KEPT_COLUMNS = {"id", "revision", "base_dn", "user_filter", "connect_timeout_seconds", "updated_at"}
OTHER_TABLES = ("users", "auth_sessions", "deals", "storage_settings")
OLD_ROW = (
    "insert into directory_settings (id, revision, server_urls, use_starttls, bind_template,"
    " base_dn, user_filter, display_name_attribute, email_attribute, connect_timeout_seconds,"
    " receive_timeout_seconds, updated_at) values (1, 3,"
    " cast('[\"ldaps://dc1.corp.test\"]' as jsonb), false, 'cn={login_id},dc=corp', 'dc=corp',"
    " '(cn={login_id})', 'displayName', 'mail', 5, 10, now())"
)


async def _old_settings_and_a_user(session: AsyncSession) -> None:
    await insert_user(session, "kim")
    await session.execute(text(OLD_ROW))


async def _new_settings_user_and_hash(session: AsyncSession) -> None:
    user_id = await insert_user(session, "kim")
    await insert_settings(session)
    await insert_password_hash(session, user_id)


async def test_upgrade_deletes_existing_directory_row_and_creates_hash_table(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 기존 설정 행이 지워지고 새 구조가 되며 해시 테이블이 비어 있다."""
    # Given
    await given_schema_at(blank_database, PARTNER_MEETINGS_REVISION)
    await given_rows(blank_database, _old_settings_and_a_user)
    assert await run_sql(blank_database, "select count(*) from directory_settings") == [(1,)]
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, directory_service_account_revision())
    assert await run_sql(blank_database, "select count(*) from directory_settings") == [(0,)]
    assert "user_password_hashes" in await table_names(blank_database)
    assert await run_sql(blank_database, "select count(*) from user_password_hashes") == [(0,)]
    columns = set(await column_names(blank_database, "directory_settings"))
    assert columns == NEW_COLUMNS | KEPT_COLUMNS | {"updated_by_user_id"}
    assert not (columns & OLD_COLUMNS)


async def test_upgrade_keeps_users_and_other_tables_untouched(blank_database: URL) -> None:
    """Scenario: 사용자 행과 다른 테이블 구조는 올려도 그대로다(기존 세션도 유지된다)."""
    # Given
    await given_schema_at(blank_database, PARTNER_MEETINGS_REVISION)
    await given_rows(blank_database, _old_settings_and_a_user)
    before = {name: await table_structure(blank_database, name) for name in OTHER_TABLES}
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert {name: await table_structure(blank_database, name) for name in OTHER_TABLES} == before
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]


async def test_upgrade_without_a_directory_row_still_creates_the_new_structure(
    blank_database: URL,
) -> None:
    """Scenario: 설정 행이 없던 DB(최초 설치 전)도 새 구조로 올라간다."""
    # Given
    await given_schema_at(blank_database, PARTNER_MEETINGS_REVISION)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, directory_service_account_revision())
    assert set(await column_names(blank_database, "directory_settings")) >= NEW_COLUMNS
    assert "user_password_hashes" in await table_names(blank_database)


async def test_upgrade_to_head_ends_at_the_directory_service_account_revision(
    blank_database: URL,
) -> None:
    """Scenario: 빈 DB를 head로 올리면 이 리비전에 이른다(head는 이 리비전이다)."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, directory_service_account_revision())


async def test_downgrade_restores_old_columns_and_drops_hash_table(blank_database: URL) -> None:
    """Scenario: 내리면 해시 테이블이 사라지고 설정 행은 비며 구 컬럼 구조로 돌아간다."""
    # Given
    await given_schema_at(blank_database, directory_service_account_revision())
    await given_rows(blank_database, _new_settings_user_and_hash)
    # When
    await when_operator_downgrades(blank_database, target=PARTNER_MEETINGS_REVISION)
    # Then
    await then_schema_is_at(blank_database, PARTNER_MEETINGS_REVISION)
    assert "user_password_hashes" not in await table_names(blank_database)
    assert await run_sql(blank_database, "select count(*) from directory_settings") == [(0,)]
    columns = set(await column_names(blank_database, "directory_settings"))
    assert columns >= OLD_COLUMNS
    assert not (columns & NEW_COLUMNS)
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]


async def test_downgrade_then_upgrade_again_reaches_the_same_structure(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 구조가 된다(롤백 뒤 재배포)."""
    # Given
    await given_schema_at(blank_database, directory_service_account_revision())
    first = {
        name: await table_structure(blank_database, name)
        for name in ("directory_settings", "user_password_hashes")
    }
    await when_operator_downgrades(blank_database, target=PARTNER_MEETINGS_REVISION)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    again = {
        name: await table_structure(blank_database, name)
        for name in ("directory_settings", "user_password_hashes")
    }
    assert again == first
