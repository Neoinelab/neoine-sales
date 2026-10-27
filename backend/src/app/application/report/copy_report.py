from typing import TYPE_CHECKING

from app.application.ids import new_report_id
from app.application.report.execution import prepare_content

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportMetaInput, ReportViewer
    from app.domain.saved_report.entities import Report
    from app.domain.saved_report.values import ReportId


class CopyReport:
    """볼 수 있는 리포트를 새 이름·공개 범위로 복제한다. 정의는 원본 그대로, 만든 사람은 요청자."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, report_id: ReportId, meta: ReportMetaInput, viewer: ReportViewer
    ) -> Report:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            source = await uow.saved_reports.get(report_id)
            source.ensure_visible_to(viewer.user_id, viewer.role)
            content = await prepare_content(  # 원본 정의도 지금 규칙으로 다시 검증한다
                uow,
                now,
                name=meta.name,
                description=meta.description,
                visibility=meta.visibility,
                definition=source.readable_definition(),
            )
            copied = source.copy_as(
                entity_id=await new_report_id(uow.ids),
                meta_name=content.name,
                meta_description=content.description,
                visibility=content.visibility,
                generated_sql=content.generated_sql,
                owner=viewer.user_id,
                now=now,
            )
            await uow.saved_reports.add(copied)
            await uow.commit()
        return copied
