"""ReportQueryRunner Port의 Fake: SQL 엔진을 흉내 내지 않는다.

받은 `ResolvedReport`를 기록하고 미리 정한 `ReportRows`(또는 예외)를 돌려준다. SQL 구현의 동작은
`tests/unit/repositories/test_report_query_*_contract.py`가 실제 DB로 검증한다(Fake와 SQL이 같은
결과를 내는 공통 계약은 없다. 계획 4.7 "Fake 방침").

domain/application 모듈은 호출 시점에 가져온다(구현 전에도 FakeUnitOfWork를 쓰는 다른 테스트의
수집이 막히지 않게).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.report_query_runner import ReportCell, ReportRows
    from app.domain.report.resolve import ResolvedReport


RENDERED_SQL = (
    "SELECT rendered_by_fake"  # render_sql이 돌려주는 고정 문자열(저장 리포트 테스트가 쓴다)
)


class FakeReportQueryRunner:
    def __init__(self) -> None:
        self.calls: list[ResolvedReport] = []
        self.error: Exception | None = None
        self.rendered: list[ResolvedReport] = []  # render_sql에 넘어온 정의(실행하지 않는다)
        self._response: ReportRows | None = None

    def respond_with(
        self,
        rows: Sequence[Sequence[ReportCell]] = (),
        *,
        total_count: int | None = None,
        totals: Sequence[ReportCell] | None = None,
        sql: str = "SELECT 1",
        elapsed_ms: int = 1,
    ) -> None:
        from app.application.ports.report_query_runner import ReportRows  # noqa: PLC0415

        self._response = ReportRows(
            rows=tuple(tuple(row) for row in rows),
            total_count=len(rows) if total_count is None else total_count,
            sql=sql,
            elapsed_ms=elapsed_ms,
            totals=None if totals is None else tuple(totals),
        )

    def render_sql(self, report: ResolvedReport) -> str:
        """실행하지 않고 표시용 SQL만 돌려준다: 받은 값을 기록하고 고정 문자열을 낸다."""
        self.rendered.append(report)
        return RENDERED_SQL

    async def run(self, report: ResolvedReport) -> ReportRows:
        self.calls.append(report)
        if self.error is not None:
            raise self.error
        if self._response is None:
            self.respond_with()
        response: Any = self._response
        return response  # type: ignore[no-any-return]
