"""Feature: 운영자는 빈 DB를 최초 리비전(00c3126aa926) 하나로 현재 스키마와 기본 시드까지 올린다.

When: 운영자 명령(alembic upgrade/downgrade). 운영자에게 공개된 인터페이스는 HTTP가 아니라
이 명령이다. 과거 리비전 체인은 2026-11-05에 최초 리비전 하나로 통합되었고, 최초 리비전은
되돌릴 수 없다(DB를 새로 만든다).
"""

from typing import TYPE_CHECKING

import pytest
from alembic.util.exc import CommandError

from tests.functional.steps.schema import (
    table_names,
    table_structure,
    then_command_aborted,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)
from tests.support.raw_sql import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

BASELINE = "00c3126aa926"
SEEDED = {"codes": 13, "bant_labels": 23, "action_types": 8}
APP_TABLES = {
    "users",
    "login_failures",
    "directory_settings",
    "user_password_hashes",
    "auth_settings",
    "auth_sessions",
    "contacts",
    "codes",
    "bant_labels",
    "action_types",
    "vendors",
    "deals",
    "deal_partners",
    "deal_bant_labels",
    "deal_history",
    "deal_actions",
    "deal_attachments",
    "storage_settings",
    "alert_settings",
    "forecast_snapshots",
    "forecast_snapshot_columns",
    "forecast_snapshot_cells",
    "reports",
    "partner_meetings",
    "license_contracts",
    "license_contract_attachments",
}
EN_DASH = chr(0x2013)


async def _row_count(url: URL, table: str) -> int:
    rows = await run_sql(url, f"select count(*) from {table}")  # noqa: S608 - 상수 이름
    return int(rows[0][0])


async def test_operator_upgrade_to_head_creates_exactly_the_current_tables(
    blank_database: URL,
) -> None:
    """Scenario: 빈 DB에 head까지 올리면 현재 테이블 26개와 alembic_version만 생긴다."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert len(APP_TABLES) == 26
    assert await table_names(blank_database) == {*APP_TABLES, "alembic_version"}
    await then_schema_is_at(blank_database, BASELINE)


async def test_a_new_database_holds_only_the_default_catalog(blank_database: URL) -> None:
    """Scenario: 새 DB에는 기본 코드·BANT Label·Action 유형만 있고 나머지 테이블은 비어 있다."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    for table in sorted(APP_TABLES):
        expected = SEEDED.get(table, 0)
        assert await _row_count(blank_database, table) == expected, table
    hints = await run_sql(
        blank_database,
        "select probability_hint from codes where kind = 'forecast' and key = 'best'",
    )
    assert hints == [(f"51{EN_DASH}75",)]


async def test_operator_downgrade_of_the_baseline_is_refused_and_changes_nothing(
    blank_database: URL,
) -> None:
    """Scenario: 최초 리비전을 base로 내리려 하면 거부되고 스키마가 그대로 남는다."""
    # Given
    await when_operator_upgrades(blank_database)
    tables_before = await table_names(blank_database)
    # When
    outcome = await when_operator_attempts_downgrade(blank_database, target="base")
    # Then
    then_command_aborted(outcome, "최초 리비전", "DB를 새로 만드세요")
    await then_schema_is_at(blank_database, BASELINE)
    assert await table_names(blank_database) == tables_before


async def test_upgrading_a_database_already_at_head_changes_nothing(blank_database: URL) -> None:
    """Scenario: 이미 head인 DB에 upgrade head를 다시 실행해도 아무것도 바뀌지 않는다."""
    # Given
    await when_operator_upgrades(blank_database)
    structure_before = {t: await table_structure(blank_database, t) for t in sorted(APP_TABLES)}
    counts_before = {t: await _row_count(blank_database, t) for t in sorted(APP_TABLES)}
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, BASELINE)
    structure_after = {t: await table_structure(blank_database, t) for t in sorted(APP_TABLES)}
    counts_after = {t: await _row_count(blank_database, t) for t in sorted(APP_TABLES)}
    assert structure_after == structure_before
    assert counts_after == counts_before


async def test_a_database_left_at_a_retired_revision_cannot_be_upgraded(
    blank_database: URL,
) -> None:
    """Scenario: 통합 전 리비전 id가 남은 DB는 upgrade가 실패하고 스키마는 바뀌지 않는다."""
    # Given
    await run_sql(
        blank_database, "create table alembic_version (version_num varchar(32) primary key)"
    )
    await run_sql(blank_database, "insert into alembic_version values ('f2b7c9e4a615')")
    # When
    with pytest.raises(CommandError):
        await when_operator_upgrades(blank_database)
    # Then
    assert await table_names(blank_database) == {"alembic_version"}
    await then_schema_is_at(blank_database, "f2b7c9e4a615")
