from typing import TYPE_CHECKING

from app.application.report.execution import report_context, result_view
from app.domain.report.parse import parse_report_definition
from app.domain.report.resolve import resolve_report

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.views import ReportResultView
    from app.domain.report.raw import RawReportDefinition


class RunReport:
    """리포트 정의를 검증하고 업무 날짜 기준으로 풀어 읽기 전용으로 실행한다(저장하지 않는다)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, raw: RawReportDefinition) -> ReportResultView:
        definition = parse_report_definition(raw)  # 위반이면 DB를 열기 전에 중단
        now = self._clock.now()
        async with self._uow_factory() as uow:
            context = await report_context(uow, now)
            result = await uow.reports.run(resolve_report(definition, context))
        return result_view(definition, result, context.today)
