"""예전 형식으로 저장된 정의를 새 형식으로 읽은 뒤 실제로 실행한 결과 값(SQL 전용).

저장 JSON → `definition_from_json` → 검증 → 해석 → `SqlReportQueryRunner.run` 경로를 그대로 따라가
결과 행의 값(코드 칸 이름, 집계 값, 정렬 순서)을 확인한다.
읽기 변환 자체는 `domain/test_report_stored.py`,
상세·실행 유스케이스의 모양은 `application/test_report_legacy_definition.py`가 본다.
"""

from typing import TYPE_CHECKING, Any

from app.domain.report.parse import parse_report_definition
from app.domain.report.resolve import resolve_report
from app.domain.report.stored import definition_from_json
from tests.support.report_defs import context

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase


async def _run_stored(case: ReportCase, stored_json: dict[str, Any]) -> list[tuple[Any, ...]]:
    """저장 JSON을 읽어 검증·해석한 뒤 SQL 실행기로 실행한 결과 행."""
    report = resolve_report(parse_report_definition(definition_from_json(stored_json)), context())
    return [tuple(row) for row in (await case.runner.run(report)).rows]


async def test_legacy_code_formats_run_with_names_not_keys(report_case: ReportCase) -> None:
    """예전 key·name 포맷으로 저장된 Status·Forecast 칸은 key가 아니라 이름으로 나온다.

    테스트 코드: RQ-109
    """
    # given: Pipeline Deal 한 건과 예전 텍스트·코드·앞 N자 포맷으로 저장된 정의
    await report_case.add_deal(name="Alpha", forecast="pipeline")
    stored = {
        "columns": [
            {"field": "deal.name", "format": "as_is"},
            {"field": "deal.status", "format": "name"},
            {"field": "deal.forecast", "format": "key"},
            {"field": "deal.code", "format": "prefix", "prefix_length": 5},
        ],
        "conditions": [],
        "combine": "and",
        "sort": None,
        "row_limit": 100,
    }
    # when: 저장 정의를 읽어 실행한다
    rows = await _run_stored(report_case, stored)
    # then: Status·Forecast 칸이 key("prospecting"·"pipeline")가 아니라 이름이다
    (row,) = rows
    assert row[0] == "Alpha"
    assert row[1] == "기회발굴"
    assert row[2] == "Pipeline"


async def test_legacy_number_formats_run_as_plain_sums(report_case: ReportCase) -> None:
    """예전 구성비 포맷으로 저장된 금액 합계 칸은 구성비가 아니라 금액 합계로 나온다.

    테스트 코드: RQ-110
    """
    # given: Vendor SAP의 금액 100·200 Deal과 예전 숫자 포맷으로 저장된 정의
    sap = await report_case.deals.new_vendor("SAP")
    await report_case.add_deal(amount=100, vendor_id=sap.id)
    await report_case.add_deal(amount=200, vendor_id=sap.id)
    stored = {
        "columns": [
            {"field": "deal.vendor", "group": True},
            {"field": "deal.amount", "aggregate": "sum", "format": "percent_share"},
            {"field": "deal.users", "aggregate": "sum", "format": "krw_million"},
            {"field": "deal.code", "aggregate": "count", "format": "decimal1"},
        ],
        "conditions": [],
        "combine": "and",
        "row_limit": 100,
    }
    # when: 저장 정의를 읽어 실행한다
    rows = await _run_stored(report_case, stored)
    # then: 첫 행의 Vendor와 금액 합계가 ["SAP", 300]이다
    assert rows[0][:2] == ("SAP", 300)


async def test_legacy_top_level_sort_runs_in_the_same_order(report_case: ReportCase) -> None:
    """예전 최상위 정렬(Vendor 내림차순)로 저장된 정의는 같은 순서로 실행된다.

    테스트 코드: RQ-111
    """
    # given: Alpha(IBM)·Beta(SAP) Deal과 예전 최상위 정렬을 가진 저장 정의
    ibm = await report_case.deals.new_vendor("IBM")
    sap = await report_case.deals.new_vendor("SAP")
    await report_case.add_deal(name="Alpha", vendor_id=ibm.id)
    await report_case.add_deal(name="Beta", vendor_id=sap.id)
    stored = {
        "columns": [{"field": "deal.name"}, {"field": "deal.vendor"}],
        "conditions": [],
        "combine": "and",
        "sort": {"column": 1, "direction": "desc"},
        "row_limit": 100,
    }
    # when: 저장 정의를 읽어 실행한다
    rows = await _run_stored(report_case, stored)
    # then: Vendor 내림차순이라 Beta(SAP)가 먼저다
    assert rows == [("Beta", "SAP"), ("Alpha", "IBM")]


async def test_legacy_solution_key_runs_as_the_product_field(report_case: ReportCase) -> None:
    """예전 key deal.solution 컬럼·조건으로 저장된 정의는 Product 값으로 실행된다.

    테스트 코드: RQ-116
    """
    # given: Product가 "ITDR"·"MFA"인 Deal 두 건과 예전 key를 쓰는 저장 정의
    await report_case.add_deal(name="Alpha", product="ITDR")
    await report_case.add_deal(name="Beta", product="MFA")
    stored = {
        "columns": [
            {"field": "deal.solution", "label": "솔루션"},
            {"field": "deal.name"},
        ],
        "conditions": [{"field": "deal.solution", "operator": "contains", "value": "itd"}],
        "combine": "and",
        "row_limit": 100,
    }
    # when: 저장 정의를 읽어 실행한다
    rows = await _run_stored(report_case, stored)
    # then: "ITDR" Deal 1행만 나온다
    assert rows == [("ITDR", "Alpha")]
