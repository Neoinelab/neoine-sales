from typing import TYPE_CHECKING

from app.domain.saved_report.layout import parse_layout

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportViewer
    from app.domain.report.raw import RawLayout
    from app.domain.saved_report.entities import Report
    from app.domain.saved_report.values import ReportId


class ChangeReportLayout:
    """결과 배치만 바꾼다. 정의·차트·이름은 건드리지 않는다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self,
        report_id: ReportId,
        layout: RawLayout,
        expected_revision: int,
        viewer: ReportViewer,
    ) -> Report:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            report = await uow.saved_reports.get(report_id, for_update=True)
            report.ensure_visible_to(viewer.user_id, viewer.role)  # 숨겨야 하는 404가 먼저
            report.readable_definition()  # 깨진 정의는 바꾸기 전에 stored-invalid 422
            parsed = parse_layout(layout)
            report.change_layout(
                parsed,
                editor=viewer.user_id,
                role=viewer.role,
                expected_revision=expected_revision,
                now=now,
            )
            await uow.saved_reports.update_layout(report)
            await uow.commit()
        return report
