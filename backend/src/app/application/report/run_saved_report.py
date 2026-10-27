from typing import TYPE_CHECKING

from app.application.report.execution import report_context, result_view
from app.domain.report.parse import parse_report_definition
from app.domain.report.resolve import resolve_report

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportViewer
    from app.application.report.views import ReportResultView
    from app.domain.saved_report.values import ReportId


class RunSavedReport:
    """저장된 정의를 지금 규칙으로 다시 검증하고 오늘 날짜로 풀어 읽기 전용으로 실행한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, report_id: ReportId, viewer: ReportViewer) -> ReportResultView:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            report = await uow.saved_reports.get(report_id)
            report.ensure_visible_to(viewer.user_id, viewer.role)
            definition = parse_report_definition(report.readable_definition())
            context = await report_context(uow, now)
            result = await uow.reports.run(resolve_report(definition, context))
        return result_view(definition, result, context.today)
