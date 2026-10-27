from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportViewer
    from app.domain.saved_report.entities import Report
    from app.domain.saved_report.values import ReportId


class GetReport:
    """저장 리포트 하나. 없거나 볼 수 없으면 같은 NotFound."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, report_id: ReportId, viewer: ReportViewer) -> Report:
        async with self._uow_factory() as uow:
            report = await uow.saved_reports.get(report_id)
        report.ensure_visible_to(viewer.user_id, viewer.role)
        report.readable_definition()
        return report
