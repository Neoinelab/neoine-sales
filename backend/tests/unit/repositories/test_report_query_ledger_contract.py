"""ReportQueryRunner(SQL) 계약: Vendor x 분기 리포트가 Deals 목록 원장과 같다.

기대값은 Deal 저장소의 `search`(목록과 같은 조건 판정)로 구한 건수·금액이다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from tests.support.report_defs import col, cond

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

QUARTER_DAYS = [date(2026, 2, 10), date(2026, 5, 10), date(2026, 8, 10), date(2026, 11, 10)]
COLUMNS = [
    col("deal.vendor", group=True),
    col("deal.expected_close", format="quarter", group=True, sort="asc"),
    col("deal.amount", aggregate="sum", label="금액 합계"),
    col("deal.code", aggregate="count", label="건수"),
]
CONDITIONS = [
    cond("deal.forecast_outcome", "not_in", ["lost"]),
    cond("deal.expected_close", "relative", {"period": "this_year"}),
]


async def _seed(case: ReportCase) -> list[int]:
    sap = await case.deals.new_vendor("SAP")
    ibm = await case.deals.new_vendor("IBM")
    oracle = await case.deals.new_vendor("Oracle")
    vendors: list[int] = [sap.id, ibm.id, oracle.id]
    amount = 1000
    for index, vendor_id in enumerate(vendors):
        for quarter, day in enumerate(QUARTER_DAYS):
            amount += 111
            forecast = "commit" if (index + quarter) % 2 else "pipeline"
            await case.add_deal(vendor_id=vendor_id, day=day, amount=amount, forecast=forecast)
    await case.add_deal(vendor_id=sap.id, day=date(2026, 5, 11), amount=5000, forecast="won")
    await case.add_deal(vendor_id=sap.id, day=date(2026, 2, 11), amount=70000, forecast="lost")
    await case.add_deal(vendor_id=oracle.id, day=date(2026, 8, 11), amount=80000, forecast="lost")
    await case.add_deal(vendor_id=sap.id, day=date(2025, 12, 31), amount=900000)
    await case.add_deal(vendor_id=ibm.id, day=date(2027, 1, 1), amount=900001)
    return vendors


async def _ledger(case: ReportCase, **criteria: object) -> tuple[int, int]:
    query = DealQuery(
        year=2026,
        forecast_outcome=ForecastOutcomeFilter.NOT_LOST,
        limit=200,
        **criteria,  # type: ignore[arg-type]
    )
    found = await case.deals.deals.search(query)
    return len(found), sum(item.deal.details.revenue_amount.value for item in found)


async def test_vendor_by_quarter_cells_equal_the_deal_list_ledger(report_case: ReportCase) -> None:
    """Vendorx분기 금액 합계·건수는 Deals 목록 원장과 같다.

    테스트 코드: RQ-046
    """
    # given: Vendor·분기·Forecast가 섞인 Deal과 Lost·다른 해 Deal 시드
    sap, ibm, oracle = await _seed(report_case)
    names = {sap: "SAP", ibm: "IBM", oracle: "Oracle"}

    # when: Vendorx분기 그룹과 금액 합계·건수로 조회한다
    rows = await report_case.rows(COLUMNS, CONDITIONS)

    # then: 칸마다 목록 원장의 건수·금액과 같다
    cells = {(row[0], row[1]): (row[3], row[2]) for row in rows}
    for vendor_id in (sap, ibm, oracle):
        for quarter in range(1, 5):
            expected = await _ledger(
                report_case, quarters=frozenset({quarter}), vendor_id=vendor_id
            )
            assert cells[(names[vendor_id], f"2026 Q{quarter}")] == expected, (vendor_id, quarter)


async def test_vendor_cells_add_up_to_the_quarter_ledger(report_case: ReportCase) -> None:
    """모든 Deal이 Vendor를 가지므로 분기별 Vendor 칸의 합은 그 분기의 목록 원장과 같다.

    테스트 코드: RQ-046
    """
    # given: Vendor·분기가 섞인 Deal 시드
    await _seed(report_case)

    # when: Vendorx분기로 조회한다
    rows = await report_case.rows(COLUMNS, CONDITIONS)

    # then: 분기마다 Vendor 칸들의 (건수, 금액) 합이 분기 원장과 같다
    for quarter in range(1, 5):
        whole = await _ledger(report_case, quarters=frozenset({quarter}))
        cells = [(row[3], row[2]) for row in rows if row[1] == f"2026 Q{quarter}"]
        assert (sum(c for c, _ in cells), sum(a for _, a in cells)) == whole, quarter


async def test_the_report_has_one_row_per_vendor_and_quarter_with_deals(
    report_case: ReportCase,
) -> None:
    """Deal이 있는 Vendorx분기마다 한 행이다.

    테스트 코드: RQ-046
    """
    # given: Vendor·분기가 섞인 Deal 시드
    await _seed(report_case)

    # when: Vendorx분기로 조회한다
    rows = await report_case.rows(COLUMNS, CONDITIONS)

    # then: 12행이다(연도 밖·Lost만 있는 칸은 없다)
    assert len(rows) == 12  # Vendor 3개 x 분기 4개. 연도 밖·Lost만 있는 칸은 없다.


async def test_lost_and_other_year_deals_are_left_out_of_the_cells(report_case: ReportCase) -> None:
    """Lost와 다른 해 Deal은 칸에서 빠진다.

    테스트 코드: RQ-046
    """
    # given: Lost·다른 해 Deal이 있는 시드
    await _seed(report_case)

    # when: Vendorx분기로 조회한다
    rows = await report_case.rows(COLUMNS, CONDITIONS)

    # then: 건수 합과 금액 합이 목록 원장과 같다
    total_amount = sum(row[2] for row in rows)
    ledger = await _ledger(report_case)
    assert (sum(row[3] for row in rows), total_amount) == ledger


async def test_grouped_totals_equal_the_ledger_of_the_same_conditions(
    report_case: ReportCase,
) -> None:
    """합계 행은 같은 조건의 원장과 같고 total_count는 그룹 수다.

    테스트 코드: RQ-046
    """
    # given: Vendor·분기가 섞인 Deal 시드
    await _seed(report_case)

    # when: Vendorx분기로 조회한다
    result = await report_case.run(COLUMNS, CONDITIONS)

    # then: 합계 행의 금액은 원장 금액, 그룹 칸은 None, 총 그룹은 12다
    _count, amount = await _ledger(report_case)
    assert result.totals is not None
    assert result.totals[0] is None  # 그룹 컬럼
    assert result.totals[1] is None
    assert result.totals[2] == amount
    assert result.total_count == 12  # total_count는 그룹 수
