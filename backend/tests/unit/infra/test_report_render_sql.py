"""SqlReportQueryRunner.render_sql (AC1): 실행하지 않고 표시용 SQL만 만든다.

`render_sql`이 돌려주는 문자열은 `run`의 `ReportRows.sql`과 같아야 한다(같은 변환 함수). 세션을
한 번도 부르지 않는다는 점은 Mock 세션으로, run과의 일치는 실제 DB 계약 테스트
(`tests/unit/repositories/test_report_render_sql_contract.py`)로 확인한다.
"""

from unittest.mock import MagicMock

from app.infra.db.report_render import display_sql
from app.infra.db.report_runner import SqlReportQueryRunner
from app.infra.db.report_select import build_select
from tests.support.report_defs import col, cond, resolved


def test_render_sql_returns_the_display_sql_of_the_data_statement() -> None:
    report = resolved(
        [col("deal.vendor", group=True), col("deal.amount")],
        [cond("deal.name", "contains", "abc")],
    )
    runner = SqlReportQueryRunner(MagicMock())

    assert runner.render_sql(report) == display_sql(build_select(report))


def test_render_sql_does_not_touch_the_session() -> None:
    session = MagicMock()
    runner = SqlReportQueryRunner(session)

    sql = runner.render_sql(resolved([col("deal.code")]))

    assert sql.startswith("SELECT")
    assert session.mock_calls == []  # execute·begin 등 어떤 호출도 없다


def test_render_sql_differs_by_definition() -> None:
    runner = SqlReportQueryRunner(MagicMock())

    simple = runner.render_sql(resolved([col("deal.code")]))
    grouped = runner.render_sql(resolved([col("deal.vendor", group=True), col("deal.amount")]))

    assert simple != grouped
