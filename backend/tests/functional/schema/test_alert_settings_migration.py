"""Feature: 운영자는 경고 기준 리비전(M-P3)을 올리고 내려 alert_settings와 Status 진입 컬럼을 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 첨부 파일 리비전(M-P2b) 다음이다.
컬럼·테이블 추가와 기존 Deal 행의 backfill(`status_changed_at` = `created_at`)뿐이고 행은 지우지
않는다. 내리면 추가한 테이블과 컬럼만 사라진다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import alert_settings_revision, attachments_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
UPDATED = datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)
STATUS_COLUMN = (
    "select data_type, is_nullable from information_schema.columns"
    " where table_name = 'deals' and column_name = 'status_changed_at'"
)


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: M-P3 리비전까지 올린다(head는 이후 리비전으로 앞서갈 수 있다)."""
    await upgrade_database(url, target=alert_settings_revision())


async def _two_deals(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    for code in ("20261016-A001", "20261016-A002"):
        await insert_deal(session, customer, owner, code=code)
    await session.execute(
        text("update deals set created_at = :created, updated_at = :updated"),
        {"created": CREATED, "updated": UPDATED},
    )


async def test_upgrade_creates_the_table_and_the_column(blank_database: URL) -> None:
    """Scenario: 올리면 alert_settings 테이블과 deals.status_changed_at(NOT NULL)이 생긴다."""
    # Given
    await given_schema_at(blank_database, attachments_revision())
    assert "alert_settings" not in await table_names(blank_database)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, alert_settings_revision())
    assert "alert_settings" in await table_names(blank_database)
    assert await run_sql(blank_database, STATUS_COLUMN) == [("timestamp with time zone", "NO")]


async def test_upgrade_fills_existing_deals_with_their_creation_time(blank_database: URL) -> None:
    """Scenario: 기존 Deal 행의 status_changed_at은 created_at(수정 시각이 아님)으로 채워진다."""
    # Given
    await given_schema_at(blank_database, attachments_revision())
    await given_rows(blank_database, _two_deals)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    rows = await run_sql(
        blank_database,
        "select count(*) from deals"
        " where status_changed_at = created_at and status_changed_at <> updated_at",
    )
    assert rows == [(2,)]


async def test_upgrade_keeps_the_existing_rows_and_seeds_no_alert_row(blank_database: URL) -> None:
    """Scenario: 올려도 Deal 행은 지워지지 않고 경고 기준 행은 없다(기본값은 앱이 준다)."""
    # Given
    await given_schema_at(blank_database, attachments_revision())
    await given_rows(blank_database, _two_deals)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from deals") == [(2,)]
    assert await run_sql(blank_database, "select count(*) from alert_settings") == [(0,)]


async def test_downgrade_removes_the_table_and_the_column_and_keeps_the_deals(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 둘 다 사라지고 deals 구조는 올리기 전과 같으며 행은 그대로다."""
    # Given
    await given_schema_at(blank_database, attachments_revision())
    await given_rows(blank_database, _two_deals)
    before = await table_structure(blank_database, "deals")
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=attachments_revision())
    # Then
    await then_schema_is_at(blank_database, attachments_revision())
    assert "alert_settings" not in await table_names(blank_database)
    assert await table_structure(blank_database, "deals") == before
    assert await run_sql(blank_database, "select count(*) from deals") == [(2,)]


async def test_upgrade_after_downgrade_creates_the_same_structure_again(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 구조가 만들어진다."""
    # Given
    await given_schema_at(blank_database, attachments_revision())
    await when_operator_upgrades(blank_database)
    first = {
        name: await table_structure(blank_database, name) for name in ("alert_settings", "deals")
    }
    await when_operator_downgrades(blank_database, target=attachments_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    second = {name: await table_structure(blank_database, name) for name in first}
    assert second == first
    await then_schema_is_at(blank_database, alert_settings_revision())
