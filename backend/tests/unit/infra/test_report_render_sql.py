"""SqlReportQueryRunner.render_sql: 실행하지 않고 표시용 SQL만 만든다.

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
    """표시 SQL은 데이터 문장의 표시용 변환 결과와 같다.

    테스트 코드: RQ-059
    """
    # given: 그룹핑과 텍스트 조건이 있는 풀린 정의
    report = resolved(
        [col("deal.vendor", group=True), col("deal.amount")],
        [cond("deal.name", "contains", "abc")],
    )
    # when: 실행기에서 표시 SQL을 만든다
    runner = SqlReportQueryRunner(MagicMock())

    # then: 데이터 문장의 표시용 변환 결과와 같다
    assert runner.render_sql(report) == display_sql(build_select(report))


def test_render_sql_does_not_touch_the_session() -> None:
    """표시 SQL을 만들 때 DB 세션을 전혀 쓰지 않는다.

    테스트 코드: RQ-059
    """
    # given: 호출 기록을 남기는 세션
    session = MagicMock()
    runner = SqlReportQueryRunner(session)

    # when: 표시 SQL을 만든다
    sql = runner.render_sql(resolved([col("deal.code")]))

    # then: SELECT로 시작하고 세션 호출이 없다
    assert sql.startswith("SELECT")
    assert session.mock_calls == []  # execute·begin 등 어떤 호출도 없다


def test_render_sql_differs_by_definition() -> None:
    """정의가 다르면 표시 SQL도 다르다.

    테스트 코드: RQ-059
    """
    runner = SqlReportQueryRunner(MagicMock())

    # when: 단순 정의와 그룹핑 정의의 표시 SQL을 만든다
    simple = runner.render_sql(resolved([col("deal.code")]))
    grouped = runner.render_sql(resolved([col("deal.vendor", group=True), col("deal.amount")]))

    # then: 두 SQL이 다르다
    assert simple != grouped
