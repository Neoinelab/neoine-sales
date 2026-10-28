"""저장 정의의 예전 포맷(as_is·prefix·name·key)을 SQL 저장소가 읽을 때 새 형식으로 바꾼다.

2026-10-28 포맷 정리, 컬럼별 정렬(최상위 sort -> 컬럼 sort).

Fake는 JSON을 거치지 않으므로 실제 PostgreSQL(SQL 구현)에서만 검증한다.
"""

import json
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from app.domain.auth.principal import Role
from tests.factories import NOW, later
from tests.factories_report import make_content, make_report
from tests.support.user_ids import uid
from tests.unit.repositories.saved_report_case import open_saved_report_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from tests.unit.repositories.saved_report_case import SavedReportCase

pytestmark = pytest.mark.integration

ALICE = uid("legacy-alice")
LEGACY = {
    "columns": [
        {"field": "deal.name", "format": "as_is"},
        {"field": "deal.owner", "format": "name"},
        {"field": "deal.status", "format": "key"},
        {"field": "deal.code", "format": "prefix", "prefix_length": 7},
        {"field": "deal.amount", "format": "thousands"},
    ],
    "conditions": [],
    "combine": "and",
    "sort": None,
    "row_limit": 1000,
}
LEGACY_SORT = {
    "columns": [
        {"field": "deal.code"},
        {"field": "deal.name"},
        {"field": "deal.vendor"},
    ],
    "conditions": [],
    "combine": "and",
    "sort": {"column": 1, "direction": "desc"},
    "row_limit": 1000,
}


@pytest.fixture
async def case(test_database_url: URL) -> AsyncIterator[SavedReportCase]:
    async with open_saved_report_case("sql", test_database_url) as provided:
        yield provided


async def _legacy_report(case: SavedReportCase) -> int:
    report = await case.add(make_report("예전 포맷", owner=ALICE, now=NOW))
    await case.corrupt_definition(report, json.dumps(LEGACY))
    return report.id


async def test_legacy_definition_row_is_read_in_new_shape(case: SavedReportCase) -> None:
    report_id = await _legacy_report(case)

    stored = await case.reports.get(report_id)

    assert stored.definition is not None
    columns = stored.definition.columns
    assert [c.format for c in columns] == [None, None, None, None, "thousands"]
    assert [c.prefix_length for c in columns] == [None, None, None, 7, None]


async def test_updating_a_legacy_report_stores_the_new_shape(case: SavedReportCase) -> None:
    report_id = await _legacy_report(case)
    stored = await case.reports.get(report_id)
    stored.overwrite(
        make_content("예전 포맷", definition=stored.definition),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await case.reports.update(stored)

    row = await case._session.execute(
        text("select definition from reports where id = :id"), {"id": report_id}
    )
    columns = row.scalar_one()["columns"]
    assert [c["format"] for c in columns] == [None, None, None, None, "thousands"]
    assert columns[3]["prefix_length"] == 7


async def _legacy_sort_report(case: SavedReportCase) -> int:
    report = await case.add(make_report("예전 정렬", owner=ALICE, now=NOW))
    await case.corrupt_definition(report, json.dumps(LEGACY_SORT))
    return report.id


async def test_legacy_top_level_sort_row_is_read_as_column_sort(case: SavedReportCase) -> None:
    report_id = await _legacy_sort_report(case)

    stored = await case.reports.get(report_id)

    assert stored.definition is not None
    assert [c.sort for c in stored.definition.columns] == [None, "desc", None]


async def test_updating_a_legacy_sort_report_stores_column_sort(case: SavedReportCase) -> None:
    report_id = await _legacy_sort_report(case)
    stored = await case.reports.get(report_id)
    stored.overwrite(
        make_content("예전 정렬", definition=stored.definition),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await case.reports.update(stored)

    row = await case._session.execute(
        text("select definition from reports where id = :id"), {"id": report_id}
    )
    definition = row.scalar_one()
    assert "sort" not in definition
    assert [c["sort"] for c in definition["columns"]] == [None, "desc", None]
