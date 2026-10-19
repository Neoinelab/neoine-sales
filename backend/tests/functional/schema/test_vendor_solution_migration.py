"""Feature: 운영자는 Vendor·Solution 리비전을 올리고 내려 vendors·solutions와 Deal 참조 컬럼을 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 경고 기준 리비전(M-P3) 다음이다.
deals.vendor/solution 문자열 컬럼은 버리고(데이터 이전 없음) vendor_id/solution_id FK로 바꾼다. Deal
행은 지우지 않는다. 내리면 문자열 컬럼이 빈 값으로 되살아나고 새 테이블·컬럼이 사라진다.
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
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import alert_settings_revision, vendor_solution_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: Vendor·Solution 리비전까지 올린다(head는 이후 리비전으로 앞서갈 수 있다)."""
    await upgrade_database(url, target=vendor_solution_revision())


async def _two_deals(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    for code in ("20261016-A001", "20261016-A002"):
        await insert_deal(session, customer, owner, code=code)


async def test_upgrade_creates_the_tables_and_replaces_the_text_columns(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 vendors·solutions가 생기고 deals의 문자열 컬럼이 FK 컬럼으로 바뀐다."""
    # Given
    await given_schema_at(blank_database, alert_settings_revision())
    assert {"vendors", "solutions"}.isdisjoint(await table_names(blank_database))
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, vendor_solution_revision())
    assert {"vendors", "solutions"} <= await table_names(blank_database)
    columns = await column_names(blank_database, "deals")
    assert {"vendor_id", "solution_id"} <= columns
    assert not {"vendor", "solution"} & columns


async def test_upgrade_keeps_existing_deals_with_an_empty_vendor(blank_database: URL) -> None:
    """Scenario: Deal 행이 있어도 올라가고, 행은 남으며 vendor_id·solution_id는 NULL이다."""
    # Given
    await given_schema_at(blank_database, alert_settings_revision())
    await given_rows(blank_database, _two_deals)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from deals") == [(2,)]
    assert await run_sql(
        blank_database,
        "select count(*) from deals where vendor_id is null and solution_id is null",
    ) == [(2,)]
    assert await run_sql(blank_database, "select count(*) from vendors") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from solutions") == [(0,)]


async def test_downgrade_restores_empty_text_columns_and_removes_the_new_objects(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 vendor/solution 문자열 컬럼이 빈 값으로 되살아나고 새 테이블이 사라진다."""
    # Given
    await given_schema_at(blank_database, alert_settings_revision())
    await given_rows(blank_database, _two_deals)
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=alert_settings_revision())
    # Then
    await then_schema_is_at(blank_database, alert_settings_revision())
    assert {"vendors", "solutions"}.isdisjoint(await table_names(blank_database))
    columns = await column_names(blank_database, "deals")
    assert {"vendor", "solution"} <= columns
    assert not {"vendor_id", "solution_id"} & columns
    assert await run_sql(
        blank_database,
        "select count(*) from deals where vendor = '' and solution = ''",
    ) == [(2,)]


async def test_downgrade_restores_the_deals_structure_of_the_previous_revision(
    blank_database: URL,
) -> None:
    """Scenario: 내린 뒤 deals 구조(열·제약·인덱스)는 올리기 전과 같다."""
    # Given
    await given_schema_at(blank_database, alert_settings_revision())
    before = await table_structure(blank_database, "deals")
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=alert_settings_revision())
    # Then
    assert await table_structure(blank_database, "deals") == before


async def test_upgrade_after_downgrade_creates_the_same_structure_again(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 구조가 만들어진다."""
    # Given
    await given_schema_at(blank_database, alert_settings_revision())
    await when_operator_upgrades(blank_database)
    first = {
        name: await table_structure(blank_database, name)
        for name in ("vendors", "solutions", "deals")
    }
    await when_operator_downgrades(blank_database, target=alert_settings_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    second = {name: await table_structure(blank_database, name) for name in first}
    assert second == first
    await then_schema_is_at(blank_database, vendor_solution_revision())
