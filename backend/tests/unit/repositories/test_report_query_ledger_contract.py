"""ReportQueryRunner(SQL) 계약: Vendor x 분기 리포트가 Deals 목록 원장과 같다 (AC3).

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
    col("deal.expected_close", format="quarter", group=True),
    col("deal.amount", aggregate="sum", label="금액 합계"),
    col("deal.code", aggregate="count", label="건수"),
]
CONDITIONS = [
    cond("deal.forecast_outcome", "not_in", ["lost"]),
    cond("deal.expected_close", "relative", {"period": "this_year"}),
]


async def _seed(case: ReportCase) -> list[int | None]:
    sap = await case.deals.new_vendor("SAP")
    ibm = await case.deals.new_vendor("IBM")
    vendors: list[int | None] = [sap.id, ibm.id, None]
    amount = 1000
    for index, vendor_id in enumerate(vendors):
        for quarter, day in enumerate(QUARTER_DAYS):
            amount += 111
            forecast = "commit" if (index + quarter) % 2 else "pipeline"
            await case.add_deal(vendor_id=vendor_id, day=day, amount=amount, forecast=forecast)
    await case.add_deal(vendor_id=sap.id, day=date(2026, 5, 11), amount=5000, forecast="won")
    await case.add_deal(vendor_id=sap.id, day=date(2026, 2, 11), amount=70000, forecast="lost")
    await case.add_deal(vendor_id=None, day=date(2026, 8, 11), amount=80000, forecast="lost")
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
    sap, ibm, _ = await _seed(report_case)
    names = {sap: "SAP", ibm: "IBM"}

    rows = await report_case.rows(COLUMNS, CONDITIONS, sort={"column": 1, "direction": "asc"})

    cells = {(row[0], row[1]): (row[3], row[2]) for row in rows}
    for vendor_id in (sap, ibm):
        for quarter in range(1, 5):
            expected = await _ledger(report_case, quarter=quarter, vendor_id=vendor_id)
            assert cells[(names[vendor_id], f"2026 Q{quarter}")] == expected, (vendor_id, quarter)


async def test_deals_without_a_vendor_equal_the_quarter_ledger_minus_the_vendors(
    report_case: ReportCase,
) -> None:
    sap, ibm, _ = await _seed(report_case)

    rows = await report_case.rows(COLUMNS, CONDITIONS)

    cells = {(row[0], row[1]): (row[3], row[2]) for row in rows}
    for quarter in range(1, 5):
        whole = await _ledger(report_case, quarter=quarter)
        with_vendor = [await _ledger(report_case, quarter=quarter, vendor_id=v) for v in (sap, ibm)]
        expected = (
            whole[0] - sum(c for c, _ in with_vendor),
            whole[1] - sum(a for _, a in with_vendor),
        )
        assert cells[(None, f"2026 Q{quarter}")] == expected, quarter


async def test_the_report_has_one_row_per_vendor_and_quarter_with_deals(
    report_case: ReportCase,
) -> None:
    await _seed(report_case)

    rows = await report_case.rows(COLUMNS, CONDITIONS)

    assert len(rows) == 12  # Vendor 2개 + 없음 x 분기 4개. 연도 밖·Lost만 있는 칸은 없다.


async def test_lost_and_other_year_deals_are_left_out_of_the_cells(report_case: ReportCase) -> None:
    await _seed(report_case)

    rows = await report_case.rows(COLUMNS, CONDITIONS)

    total_amount = sum(row[2] for row in rows)
    ledger = await _ledger(report_case)
    assert (sum(row[3] for row in rows), total_amount) == ledger


async def test_grouped_totals_equal_the_ledger_of_the_same_conditions(
    report_case: ReportCase,
) -> None:
    await _seed(report_case)

    result = await report_case.run(COLUMNS, CONDITIONS)

    _count, amount = await _ledger(report_case)
    assert result.totals is not None
    assert result.totals[0] is None  # 그룹 컬럼
    assert result.totals[1] is None
    assert result.totals[2] == amount
    assert result.total_count == 12  # total_count는 그룹 수
