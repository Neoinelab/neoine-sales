"""예전 형식으로 저장된 리포트 정의의 상세 조회와 실행.

저장소가 읽을 때 `definition_from_json`으로 바꾼 정의를 Fake 작업 단위에 시드해 두고,
상세 조회(GetReport)와 저장 리포트 실행(RunSavedReport)이 새 형식으로 동작하는지 본다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from app.application.report.get_report import GetReport
from app.application.report.run_saved_report import RunSavedReport
from app.domain.report.stored import definition_from_json, definition_to_json
from app.domain.report.vocabulary import Aggregate, NumberUnit, SortDirection
from tests.factories_report import make_report
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.unit.application.saved_report_env import ALICE, seed, viewer

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.ports.unit_of_work import UnitOfWorkFactory

NOW = FixedClock(datetime(2026, 10, 27, 3, 0, tzinfo=UTC))  # Seoul 2026-10-27 정오
LEGACY_TEXT = {
    "columns": [
        {"field": "deal.name", "format": "as_is"},
        {"field": "deal.status", "format": "name"},
        {"field": "deal.forecast", "format": "key"},
        {"field": "deal.code", "format": "prefix", "prefix_length": 5},
    ],
    "conditions": [],
    "combine": "and",
    "sort": None,
    "row_limit": 1000,
}
LEGACY_NUMBER = {
    "columns": [
        {"field": "deal.vendor", "group": True},
        {"field": "deal.amount", "aggregate": "sum", "format": "percent_share"},
        {"field": "deal.users", "aggregate": "sum", "format": "krw_million"},
        {"field": "deal.code", "aggregate": "count", "format": "decimal1"},
    ],
    "conditions": [],
    "combine": "and",
    "row_limit": 1000,
}
LEGACY_SORT = {
    "columns": [{"field": "deal.name"}, {"field": "deal.vendor"}],
    "conditions": [],
    "combine": "and",
    "sort": {"column": 1, "direction": "desc"},
    "row_limit": 1000,
}


LEGACY_SOLUTION = {
    "columns": [
        {"field": "deal.solution", "label": "솔루션"},
        {"field": "deal.name"},
    ],
    "conditions": [{"field": "deal.solution", "operator": "contains", "value": "itd"}],
    "combine": "and",
    "row_limit": 1000,
}


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _seed_legacy(uow: FakeUnitOfWork, stored_json: dict[str, Any]) -> Any:  # noqa: ANN401
    report = make_report("예전 형식", owner=ALICE, definition=definition_from_json(stored_json))
    await seed(uow, report)
    return report


async def test_legacy_text_and_code_formats_open_and_run_as_formatless(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """예전 텍스트·코드 포맷은 포맷 없음으로, 예전 앞 N자 포맷의 N은 앞 N자 옵션으로 열고 실행된다.

    테스트 코드: RQ-109
    """
    # given: 예전 텍스트·코드·앞 N자 포맷으로 저장된 ALICE의 리포트
    report = await _seed_legacy(uow, LEGACY_TEXT)
    # when: ALICE가 상세를 열고 실행한다
    opened = await GetReport(uow_factory).execute(report.id, viewer(ALICE))
    view = await RunSavedReport(uow_factory, NOW).execute(report.id, viewer(ALICE))
    # then: 상세의 포맷은 모두 None, 앞 N자는 [None, None, None, 5]이고 최상위 sort 없이 다시 쓰인다
    assert opened.definition is not None
    assert [c.format for c in opened.definition.columns] == [None] * 4
    assert [c.prefix_length for c in opened.definition.columns] == [None, None, None, 5]
    assert "sort" not in definition_to_json(opened.definition)
    # then: 실행에 쓰인 정의와 결과 열도 포맷이 없고 앞 N자만 남는다
    assert [c.format for c in uow.reports.calls[0].definition.columns] == [None] * 4
    assert [c.format for c in view.columns] == [None] * 4
    assert [c.prefix_length for c in view.columns] == [None, None, None, 5]


async def test_legacy_number_formats_run_as_plain_aggregates(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """예전 숫자 포맷은 포맷 없음으로 열리고 값은 집계 그대로 실행된다.

    테스트 코드: RQ-110
    """
    # given: 금액 합계·Users 합계·건수에 예전 숫자 포맷이 붙은 ALICE의 리포트
    report = await _seed_legacy(uow, LEGACY_NUMBER)
    # when: ALICE가 상세를 열고 실행한다
    opened = await GetReport(uow_factory).execute(report.id, viewer(ALICE))
    view = await RunSavedReport(uow_factory, NOW).execute(report.id, viewer(ALICE))
    # then: 상세 포맷은 모두 None이다
    assert opened.definition is not None
    assert [c.format for c in opened.definition.columns] == [None] * 4
    # then: 결과 열 포맷은 모두 None, 단위는 금액만 krw이고 집계는 그대로다
    assert [c.format for c in view.columns] == [None] * 4
    assert [c.unit for c in view.columns] == [None, NumberUnit.KRW, None, None]
    aggregates = [None, Aggregate.SUM, Aggregate.SUM, Aggregate.COUNT]
    assert [c.aggregate for c in view.columns] == aggregates


async def test_legacy_top_level_sort_runs_as_the_column_sort(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """예전 최상위 정렬은 그 컬럼의 정렬로 열리고 같은 정렬로 실행된다.

    테스트 코드: RQ-111
    """
    # given: Vendor 컬럼 내림차순을 최상위 정렬로 가진 ALICE의 리포트
    report = await _seed_legacy(uow, LEGACY_SORT)
    # when: ALICE가 상세를 열고 실행한다
    opened = await GetReport(uow_factory).execute(report.id, viewer(ALICE))
    await RunSavedReport(uow_factory, NOW).execute(report.id, viewer(ALICE))
    # then: 상세 컬럼 sort는 [None, "desc"]이고 다시 쓰면 최상위 sort가 없다
    assert opened.definition is not None
    assert [c.sort for c in opened.definition.columns] == [None, "desc"]
    assert "sort" not in definition_to_json(opened.definition)
    # then: 실행기가 받은 정의의 정렬 키는 Vendor 컬럼 내림차순 하나다
    (key,) = uow.reports.calls[0].definition.sort_keys()
    assert (key.column, key.direction) == (1, SortDirection.DESC)


async def test_legacy_solution_key_opens_and_runs_as_the_product_field(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """예전 key deal.solution으로 저장된 정의는 deal.product로 열리고 실행되며 label은 그대로다.

    테스트 코드: RQ-116
    """
    # given: 예전 key를 컬럼(label "솔루션")과 조건에 쓰는 ALICE의 저장 리포트
    report = await _seed_legacy(uow, LEGACY_SOLUTION)
    # when: ALICE가 상세를 열고 실행한다
    opened = await GetReport(uow_factory).execute(report.id, viewer(ALICE))
    view = await RunSavedReport(uow_factory, NOW).execute(report.id, viewer(ALICE))
    # then: 상세 정의의 컬럼·조건 field는 deal.product이고 컬럼 label "솔루션"은 그대로다
    assert opened.definition is not None
    assert [c.field for c in opened.definition.columns] == ["deal.product", "deal.name"]
    assert opened.definition.columns[0].label == "솔루션"
    assert [c.field for c in opened.definition.conditions] == ["deal.product"]
    # then: 실행기가 받은 정의도 Product 필드이고 첫 결과 열 이름은 "솔루션"이다
    assert [c.field.key for c in uow.reports.calls[0].definition.columns] == [
        "deal.product",
        "deal.name",
    ]
    assert view.columns[0].field == "deal.product"
    assert view.columns[0].label == "솔루션"
    # then: 다시 쓴 JSON에는 deal.solution이 없다
    assert "deal.solution" not in str(definition_to_json(opened.definition))
