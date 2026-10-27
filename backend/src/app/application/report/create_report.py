from typing import TYPE_CHECKING

from app.application.ids import new_report_id
from app.application.report.execution import prepare_content
from app.domain.saved_report.entities import Report

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportContentInput, ReportViewer


class CreateReport:
    """리포트를 저장한다. 어떤 역할이든 만들 수 있고, 만든 사람은 요청자다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, data: ReportContentInput, viewer: ReportViewer) -> Report:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            content = await prepare_content(uow, now, data)
            report = Report.create(
                entity_id=await new_report_id(uow.ids),
                content=content,
                owner=viewer.user_id,
                now=now,
            )
            await uow.saved_reports.add(report)
            await uow.commit()
        return report
