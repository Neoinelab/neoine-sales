from typing import TYPE_CHECKING

from app.application.report.saved_views import ReportItemView
from app.domain.saved_report.policy import list_scope

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.saved_inputs import ReportViewer


class ListReports:
    """요청자가 볼 수 있는 저장 리포트를 최신 수정 순으로 돌려준다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, viewer: ReportViewer) -> Sequence[ReportItemView]:
        async with self._uow_factory() as uow:
            reports = await uow.saved_reports.list(list_scope(viewer.user_id, viewer.role))
        return [ReportItemView(r, r.entities()) for r in reports]
