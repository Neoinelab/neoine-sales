from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportViewer
    from app.domain.saved_report.values import ReportId


class DeleteReport:
    """만든 사람 또는 admin이 리포트를 지운다(안 보이면 404, 보이지만 권한이 없으면 403)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, report_id: ReportId, viewer: ReportViewer) -> None:
        async with self._uow_factory() as uow:
            report = await uow.saved_reports.get(report_id, for_update=True)
            report.ensure_deletable_by(viewer.user_id, viewer.role)
            await uow.saved_reports.delete(report_id)
            await uow.commit()
