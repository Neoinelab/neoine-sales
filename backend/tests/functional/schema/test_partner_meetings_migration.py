"""Feature: 운영자는 파트너 Activity 리비전을 올리고 내려 partner_meetings 테이블을 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 Reports 배치 리비전(`b7d2e9a4c156`) 바로
다음이고 head다. `partner_meetings` 테이블 하나만 추가하는 순수 expand라 기존 테이블 구조와 행은
그대로이고(구 앱과 같은 DB에서 공존 가능), 시드 행도 없다. 내리면 그 테이블만 사라진다(기록 소실은
개발 단계라 허용).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.head_rows import insert_user
from tests.support.revisions import PARTNER_MEETINGS_REVISION, REPORTS_LAYOUT_REVISION
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

EXISTING_TABLES = ("users", "deals", "contacts", "deal_actions", "reports")


async def _one_user(session: AsyncSession) -> None:
    await insert_user(session, "kim")


async def test_upgrade_creates_the_table_and_nothing_else_changes(blank_database: URL) -> None:
    """Scenario: 올리면 partner_meetings만 생기고 기존 테이블 구조는 그대로이며 행도 남는다."""
    # Given
    await given_schema_at(blank_database, REPORTS_LAYOUT_REVISION)
    await given_rows(blank_database, _one_user)
    before_tables = await table_names(blank_database)
    before = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    assert "partner_meetings" not in before_tables
    # When
    await when_operator_upgrades(blank_database, target=PARTNER_MEETINGS_REVISION)
    # Then
    await then_schema_is_at(blank_database, PARTNER_MEETINGS_REVISION)
    assert await table_names(blank_database) == before_tables | {"partner_meetings"}
    after = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    assert after == before
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]


async def test_upgrade_seeds_no_meeting_rows(blank_database: URL) -> None:
    """Scenario: 새 테이블은 비어 있다."""
    # Given
    await given_schema_at(blank_database, REPORTS_LAYOUT_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=PARTNER_MEETINGS_REVISION)
    # Then
    assert await run_sql(blank_database, "select count(*) from partner_meetings") == [(0,)]


async def test_upgrade_to_head_ends_at_the_partner_meetings_revision(
    blank_database: URL,
) -> None:
    """Scenario: 빈 DB를 head로 올리면 이 리비전에 이른다(head는 이 리비전이다)."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, PARTNER_MEETINGS_REVISION)
    assert "partner_meetings" in await table_names(blank_database)


async def test_downgrade_drops_only_the_table(blank_database: URL) -> None:
    """Scenario: 내리면 partner_meetings만 사라지고 기존 테이블 구조와 행은 올리기 전과 같다."""
    # Given
    await given_schema_at(blank_database, REPORTS_LAYOUT_REVISION)
    await given_rows(blank_database, _one_user)
    before_tables = await table_names(blank_database)
    before = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    await when_operator_upgrades(blank_database, target=PARTNER_MEETINGS_REVISION)
    # When
    await when_operator_downgrades(blank_database, target=REPORTS_LAYOUT_REVISION)
    # Then
    await then_schema_is_at(blank_database, REPORTS_LAYOUT_REVISION)
    assert await table_names(blank_database) == before_tables
    assert {name: await table_structure(blank_database, name) for name in EXISTING_TABLES} == before
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]
