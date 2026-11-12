"""render_sql 계약(SQL 전용): 같은 정의에서 `render_sql`과 `run`이 돌려주는 SQL이 같다."""

from typing import TYPE_CHECKING

from tests.support.report_defs import col, cond, context, resolved

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase


async def test_render_sql_equals_run_sql_without_executing(report_case: ReportCase) -> None:
    """같은 정의에서 render_sql과 run이 돌려주는 SQL이 같다.

    테스트 코드: RQ-059
    """
    # given: Deal 1건과 그룹핑·조건이 있는 풀린 정의
    await report_case.add_deal(name="a", amount=10)
    report = resolved(
        [col("deal.vendor", group=True), col("deal.amount", aggregate="sum")],
        [
            cond("deal.amount", "gte", 1),
            cond("deal.expected_close", "relative", {"period": "this_year"}),
        ],
        ctx=context(),
    )

    # when: render_sql로 SQL을 만들고 run으로 실행한다
    rendered = report_case.runner.render_sql(report)
    result = await report_case.runner.run(report)

    # then: 두 SQL 문자열이 같다
    assert rendered == result.sql
