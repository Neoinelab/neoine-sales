from typing import TYPE_CHECKING

from app.application.report.execution import prepare_content

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportContentInput, ReportViewer
    from app.domain.saved_report.entities import Report
    from app.domain.saved_report.values import ReportId


class UpdateReport:
    """저장된 리포트를 덮어쓴다. 행을 잠근 채 볼 수 있는지 확인한 뒤 내용을 검증하고 교체한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self,
        report_id: ReportId,
        data: ReportContentInput,
        expected_revision: int,
        viewer: ReportViewer,
    ) -> Report:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            report = await uow.saved_reports.get(report_id, for_update=True)
            report.ensure_visible_to(viewer.user_id, viewer.role)  # 숨겨야 하는 404가 먼저
            content = await prepare_content(uow, now, data)
            report.overwrite(
                content,
                editor=viewer.user_id,
                role=viewer.role,
                expected_revision=expected_revision,
                now=now,
            )
            await uow.saved_reports.update(report)
            await uow.commit()
        return report
