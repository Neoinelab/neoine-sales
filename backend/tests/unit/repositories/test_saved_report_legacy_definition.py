"""저장 정의의 예전 포맷(as_is·prefix·name·key)을 SQL 저장소가 읽을 때 새 형식으로 바꾼다.

2026-10-28 포맷 정리.

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
