"""저장 정의의 예전 형식(포맷·최상위 정렬)을 SQL 저장소가 읽을 때 새 형식으로 바꾼다.

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
        {"field": "deal.amount", "format": "percent_share", "aggregate": "sum"},
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
    """예전 포맷 정의 행을 SQL 저장소가 읽으면 새 형식(포맷 없음, 앞 N자)이다.

    테스트 코드: RQ-109, RQ-110
    """
    # given: 예전 포맷(as_is·name·key·prefix·숫자 포맷)이 든 정의 JSON 행 (전제: 실제 DB)
    report_id = await _legacy_report(case)

    # when: 저장소에서 리포트를 읽는다
    stored = await case.reports.get(report_id)

    # then: 포맷은 모두 None이고 앞 N자는 [None, None, None, 7, None, None]이다
    assert stored.definition is not None
    columns = stored.definition.columns
    assert [c.format for c in columns] == [None] * 6
    assert [c.prefix_length for c in columns] == [None, None, None, 7, None, None]


async def test_updating_a_legacy_report_stores_the_new_shape(case: SavedReportCase) -> None:
    """예전 형식 리포트를 수정해 저장하면 새 형식으로 저장된다.

    테스트 코드: RQ-109
    """
    # given: 예전 포맷 정의 행
    report_id = await _legacy_report(case)
    stored = await case.reports.get(report_id)
    # when: 읽은 정의로 덮어써 저장한다
    stored.overwrite(
        make_content("예전 포맷", definition=stored.definition),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await case.reports.update(stored)

    # then: 저장된 JSON의 포맷은 모두 null이고 앞 N자 7이 남는다
    row = await case._session.execute(
        text("select definition from reports where id = :id"), {"id": report_id}
    )
    columns = row.scalar_one()["columns"]
    assert [c["format"] for c in columns] == [None] * 6
    assert columns[3]["prefix_length"] == 7


async def _legacy_sort_report(case: SavedReportCase) -> int:
    report = await case.add(make_report("예전 정렬", owner=ALICE, now=NOW))
    await case.corrupt_definition(report, json.dumps(LEGACY_SORT))
    return report.id


async def test_legacy_top_level_sort_row_is_read_as_column_sort(case: SavedReportCase) -> None:
    """예전 최상위 정렬 행은 컬럼 정렬로 읽힌다.

    테스트 코드: RQ-111
    """
    # given: 최상위 정렬이 있는 정의 JSON 행 (전제: 실제 DB)
    report_id = await _legacy_sort_report(case)

    # when: 저장소에서 리포트를 읽는다
    stored = await case.reports.get(report_id)

    # then: 컬럼 sort가 [None, "desc", None]이다
    assert stored.definition is not None
    assert [c.sort for c in stored.definition.columns] == [None, "desc", None]


async def test_updating_a_legacy_sort_report_stores_column_sort(case: SavedReportCase) -> None:
    """예전 정렬 리포트를 수정해 저장하면 컬럼 정렬로만 저장된다.

    테스트 코드: RQ-111
    """
    # given: 최상위 정렬이 있는 정의 행
    report_id = await _legacy_sort_report(case)
    stored = await case.reports.get(report_id)
    # when: 읽은 정의로 덮어써 저장한다
    stored.overwrite(
        make_content("예전 정렬", definition=stored.definition),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await case.reports.update(stored)

    # then: 저장된 JSON에 최상위 sort가 없고 컬럼 sort가 [None, "desc", None]이다
    row = await case._session.execute(
        text("select definition from reports where id = :id"), {"id": report_id}
    )
    definition = row.scalar_one()
    assert "sort" not in definition
    assert [c["sort"] for c in definition["columns"]] == [None, "desc", None]
