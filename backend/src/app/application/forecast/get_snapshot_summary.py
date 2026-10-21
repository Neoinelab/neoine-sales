from typing import TYPE_CHECKING

from app.application.forecast.get_summary import row_view
from app.application.forecast.views import ForecastRowView, ForecastSummaryView, SummaryBasis
from app.domain.forecast.errors import ForecastSnapshotNotFoundError

if TYPE_CHECKING:
    from app.application.ports.forecast_repository import ForecastCriteria
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.forecast.snapshot import YearMonth


class GetForecastSnapshotSummary:
    """저장된 스냅숏을 실시간 요약과 같은 모양으로 읽는다(Vendor 조건 없음)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, period: YearMonth, criteria: ForecastCriteria) -> ForecastSummaryView:
        if criteria.vendor_id is not None:
            msg = "스냅숏에는 Vendor 조건을 쓸 수 없습니다."
            raise ValueError(msg)
        async with self._uow_factory() as uow:
            snapshot = await uow.forecast_snapshots.get(period)
            if snapshot is None:
                raise ForecastSnapshotNotFoundError(period)
            summary = snapshot.summary(criteria.period, criteria.owner_user_id)
            refs = await uow.users.get_refs(
                [r.owner_id for r in summary.rows if r.owner_id is not None]
            )
        summary = summary.ordered(lambda owner: (refs[owner].resigned, refs[owner].name, owner))
        return ForecastSummaryView(
            basis=SummaryBasis.SNAPSHOT,
            as_of=snapshot.taken_at,
            snapshot_period=str(snapshot.period),
            period=criteria.period,
            columns=summary.columns,
            rows=[row_view(r, refs) for r in summary.rows],
            total=ForecastRowView(None, summary.total.cells, summary.total.open_total),
        )
