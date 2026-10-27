"""render_sql 계약(AC1, SQL 전용): 같은 정의에서 `render_sql`과 `run`이 돌려주는 SQL이 같다."""

from typing import TYPE_CHECKING

from tests.support.report_defs import col, cond, context, resolved

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase


async def test_render_sql_equals_run_sql_without_executing(report_case: ReportCase) -> None:
    await report_case.add_deal(name="a", amount=10)
    report = resolved(
        [col("deal.vendor", group=True), col("deal.amount", aggregate="sum")],
        [
            cond("deal.amount", "gte", 1),
            cond("deal.expected_close", "relative", {"period": "this_year"}),
        ],
        ctx=context(),
    )

    rendered = report_case.runner.render_sql(report)
    result = await report_case.runner.run(report)

    assert rendered == result.sql
