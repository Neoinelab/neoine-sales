"""Feature: 운영자는 앱 자체 계정 관리 리비전을 올리고 내려 auth_settings와 users.phone을 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 AD 설정 개편 리비전 다음이고 head다.
순수 expand라 기존 행은 그대로이고 `users.phone`은 NULL이다. 재직 admin이나 AD 설정 행이 이미 있는
시스템은 `auth_settings`에 `ad` 한 행을 심어(AC-14) 올린 뒤에도 지금과 같이 동작하고, 둘 다 없으면
행이 없다(방식 미선택). 내리면 phone 값과 auth_settings가 사라진다(개발 단계라 허용).
"""

from typing import TYPE_CHECKING

import pytest

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
from tests.support.directory_rows import insert_settings
from tests.support.head_rows import insert_user
from tests.support.revisions import auth_mode_revision, directory_service_account_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

OTHER_TABLES = ("deals", "auth_sessions", "directory_settings", "storage_settings")


async def _admin(session: AsyncSession) -> None:
    await insert_user(session, "boss", role="admin")


async def _sales_only(session: AsyncSession) -> None:
    await insert_user(session, "kim")


async def _directory_only(session: AsyncSession) -> None:
    await insert_settings(session)


async def _users(session: AsyncSession) -> None:
    await insert_user(session, "kim")
    await insert_user(session, "lee")


async def test_upgrade_with_an_active_admin_seeds_the_ad_mode(blank_database: URL) -> None:
    """Scenario: 재직 admin이 이미 있는 시스템은 올린 뒤 인증 방식이 ad다."""
    # Given
    await given_schema_at(blank_database, directory_service_account_revision())
    await given_rows(blank_database, _admin)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, auth_mode_revision())
    assert await run_sql(blank_database, "select id, mode from auth_settings") == [(1, "ad")]


async def test_upgrade_with_a_saved_directory_row_seeds_the_ad_mode(blank_database: URL) -> None:
    """Scenario: AD 설정 행만 있는 시스템(최초 설정 중간)도 올린 뒤 인증 방식이 ad다."""
    # Given
    await given_schema_at(blank_database, directory_service_account_revision())
    await given_rows(blank_database, _directory_only)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select id, mode from auth_settings") == [(1, "ad")]


async def test_upgrade_of_a_fresh_system_leaves_the_mode_unchosen(blank_database: URL) -> None:
    """Scenario: 아무 설정도 없던 시스템은 올린 뒤에도 행이 없다(최초 설정 1단계에서 고른다)."""
    # Given
    await given_schema_at(blank_database, directory_service_account_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from auth_settings") == [(0,)]


async def test_upgrade_with_only_non_admin_users_leaves_the_mode_unchosen(
    blank_database: URL,
) -> None:
    """Scenario: 재직 admin도 AD 설정도 없으면(일반 사용자만 있어도) 행을 심지 않는다."""
    # Given
    await given_schema_at(blank_database, directory_service_account_revision())
    await given_rows(blank_database, _sales_only)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from auth_settings") == [(0,)]


async def test_upgrade_adds_a_null_phone_and_keeps_users_and_other_tables(
    blank_database: URL,
) -> None:
    """Scenario: users에 phone(NULL)만 더해지고 사용자 행과 다른 테이블 구조는 그대로다."""
    # Given
    await given_schema_at(blank_database, directory_service_account_revision())
    await given_rows(blank_database, _users)
    before_columns = set(await column_names(blank_database, "users"))
    before = {name: await table_structure(blank_database, name) for name in OTHER_TABLES}
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert set(await column_names(blank_database, "users")) == before_columns | {"phone"}
    assert await run_sql(blank_database, "select count(*) from users") == [(2,)]
    assert await run_sql(blank_database, "select count(phone) from users") == [(0,)]
    assert {name: await table_structure(blank_database, name) for name in OTHER_TABLES} == before


async def test_upgrade_from_empty_to_head_ends_at_the_auth_mode_revision(
    blank_database: URL,
) -> None:
    """Scenario: 빈 DB를 head로 올리면 이 리비전에 이르고 auth_settings가 있다."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, auth_mode_revision())
    assert "auth_settings" in await table_names(blank_database)


async def test_downgrade_drops_the_table_and_the_phone_column(blank_database: URL) -> None:
    """Scenario: 내리면 auth_settings와 users.phone이 사라지고 사용자 행은 남는다."""
    # Given
    await given_schema_at(blank_database, auth_mode_revision())
    await given_rows(blank_database, _users)
    await run_sql(blank_database, "update users set phone = '010-1234-5678'")
    # When
    await when_operator_downgrades(blank_database, target=directory_service_account_revision())
    # Then
    await then_schema_is_at(blank_database, directory_service_account_revision())
    assert "auth_settings" not in await table_names(blank_database)
    assert "phone" not in await column_names(blank_database, "users")
    assert await run_sql(blank_database, "select count(*) from users") == [(2,)]


async def test_upgrade_again_after_a_downgrade_restores_the_structure(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다 다시 올리면 같은 구조가 된다."""
    # Given
    await given_schema_at(blank_database, auth_mode_revision())
    first = {
        name: await table_structure(blank_database, name) for name in ("auth_settings", "users")
    }
    await when_operator_downgrades(blank_database, target=directory_service_account_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    again = {
        name: await table_structure(blank_database, name) for name in ("auth_settings", "users")
    }
    assert again == first
