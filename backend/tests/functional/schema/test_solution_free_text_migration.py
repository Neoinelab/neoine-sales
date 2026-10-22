"""Feature: 운영자는 Solution 텍스트 리비전을 올리고 내려 `solutions` 목록을 텍스트 컬럼으로 바꾼다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 Forecast 스냅숏 리비전(`11bfe225caf5`)
바로 다음이고 head다. upgrade는 `deals.solution varchar(200) NOT NULL`(기본값 없음)을 추가하고
기존 `solution_id`가 가리키던 Solution 이름을 그 텍스트로 옮긴 뒤 `solutions` 테이블과
`solution_id`·복합 FK·CHECK·인덱스를 지운다. downgrade는 빈 `solutions`와 NULL `solution_id`를
되살리고 텍스트는 복원하지 않는다(소실). 개발 단계라 expand/contract의 예외다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    column_names,
    given_rows,
    given_schema_at,
    index_names,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import forecast_snapshots_revision, solution_free_text_revision
from tests.support.solution_rows import insert_solution, link_deal
from tests.support.user_fk_migration import run_sql
from tests.support.vendor_rows import insert_vendor

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

SELECTED = "20261022-A001"
VENDOR_ONLY = "20261022-A002"
NOTHING = "20261022-A003"
REMOVED_CONSTRAINTS = {"fk_deals_solution", "ck_deals_solution_needs_vendor"}
LONG_NAME = "가" * 200


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: Solution 텍스트 리비전까지 올린다."""
    await upgrade_database(url, target=solution_free_text_revision())


async def _deals_with_and_without_a_solution(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    vendor = await insert_vendor(session, "SAP")
    solution = await insert_solution(session, vendor, "S/4HANA")
    await insert_deal(session, customer, owner, code=SELECTED)
    await insert_deal(session, customer, owner, code=VENDOR_ONLY)
    await insert_deal(session, customer, owner, code=NOTHING)
    await link_deal(session, SELECTED, vendor, solution)
    await link_deal(session, VENDOR_ONLY, vendor, None)


async def _deal_with_a_200_character_solution(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    vendor = await insert_vendor(session, "SAP")
    solution = await insert_solution(session, vendor, LONG_NAME)
    await insert_deal(session, customer, owner, code=SELECTED)
    await link_deal(session, SELECTED, vendor, solution)


async def _solutions_of(url: URL) -> list[tuple[str, str]]:
    rows = await run_sql(url, "select deal_code, solution from deals order by deal_code")
    return [(str(code), str(solution)) for code, solution in rows]


async def test_upgrade_moves_solution_names_into_deal_text(blank_database: URL) -> None:
    """Scenario: 목록에서 고른 Solution 이름이 텍스트로 옮겨지고, 없던 Deal은 빈 문자열이 된다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    await given_rows(blank_database, _deals_with_and_without_a_solution)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, solution_free_text_revision())
    assert await _solutions_of(blank_database) == [
        (SELECTED, "S/4HANA"),
        (VENDOR_ONLY, ""),
        (NOTHING, ""),
    ]
    assert await run_sql(blank_database, "select count(*) from deals") == [(3,)]


async def test_upgrade_keeps_the_vendor_of_every_deal(blank_database: URL) -> None:
    """Scenario: 올려도 Vendor 참조와 vendors 행은 그대로다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    await given_rows(blank_database, _deals_with_and_without_a_solution)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from vendors") == [(1,)]
    assert await run_sql(
        blank_database, "select count(*) from deals where vendor_id is not null"
    ) == [(2,)]


async def test_upgrade_moves_a_200_character_solution_name_whole(blank_database: URL) -> None:
    """Scenario: 200자 Solution 이름도 잘리거나 실패하지 않고 그대로 옮겨진다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    await given_rows(blank_database, _deal_with_a_200_character_solution)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await _solutions_of(blank_database) == [(SELECTED, LONG_NAME)]


async def test_upgrade_drops_the_solutions_table_and_its_references(blank_database: URL) -> None:
    """Scenario: 올리면 solutions 테이블과 solution_id 컬럼·제약·인덱스가 없다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    await given_rows(blank_database, _deals_with_and_without_a_solution)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert "solutions" not in await table_names(blank_database)
    columns = await column_names(blank_database, "deals")
    assert "solution_id" not in columns
    assert {"vendor_id", "solution"} <= columns
    constraints = {
        row[0] for row in (await table_structure(blank_database, "deals"))["constraints"]
    }
    assert not REMOVED_CONSTRAINTS & constraints
    assert "fk_deals_vendor_id_vendors" in constraints
    indexes = await index_names(blank_database, "deals")
    assert "ix_deals_solution_id" not in indexes
    assert "ix_deals_vendor_id" in indexes


async def test_upgrade_makes_solution_a_not_null_varchar_200_without_default(
    blank_database: URL,
) -> None:
    """Scenario: 올린 뒤 deals.solution은 varchar(200) NOT NULL이고 DB 기본값이 없다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    columns = (await table_structure(blank_database, "deals"))["columns"]
    (solution,) = [row for row in columns if row[0] == "solution"]
    assert tuple(solution) == ("solution", "character varying(200)", True, None)


async def test_upgrade_works_on_an_empty_database(blank_database: URL) -> None:
    """Scenario: Deal이 하나도 없는 DB에도 실패 없이 올라간다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, solution_free_text_revision())
    assert "solutions" not in await table_names(blank_database)


async def test_downgrade_restores_empty_solution_structure(blank_database: URL) -> None:
    """Scenario: 내리면 빈 solutions와 NULL solution_id가 되살아나고 deals.solution은 사라진다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    await given_rows(blank_database, _deals_with_and_without_a_solution)
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=forecast_snapshots_revision())
    # Then
    await then_schema_is_at(blank_database, forecast_snapshots_revision())
    assert "solutions" in await table_names(blank_database)
    assert await run_sql(blank_database, "select count(*) from solutions") == [(0,)]
    columns = await column_names(blank_database, "deals")
    assert "solution_id" in columns
    assert "solution" not in columns
    assert await run_sql(
        blank_database, "select count(*) from deals where solution_id is not null"
    ) == [(0,)]
    assert await run_sql(blank_database, "select count(*) from deals") == [(3,)]


async def test_downgrade_restores_the_previous_table_structures(blank_database: URL) -> None:
    """Scenario: 내린 뒤 solutions·deals 구조(열·제약 이름·인덱스)는 올리기 전과 같다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    deals_before = await table_structure(blank_database, "deals")
    solutions_before = await table_structure(blank_database, "solutions")
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=forecast_snapshots_revision())
    # Then
    assert await table_structure(blank_database, "deals") == deals_before
    assert await table_structure(blank_database, "solutions") == solutions_before


async def test_upgrade_after_downgrade_gives_the_same_structure_again(blank_database: URL) -> None:
    """Scenario: 올렸다 내리고 다시 올려도 같은 구조가 만들어진다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    await when_operator_upgrades(blank_database)
    first = await table_structure(blank_database, "deals")
    await when_operator_downgrades(blank_database, target=forecast_snapshots_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await table_structure(blank_database, "deals") == first
    await then_schema_is_at(blank_database, solution_free_text_revision())
