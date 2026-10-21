from typing import TYPE_CHECKING

from app.application.forecast.views import ForecastRowView, ForecastSummaryView, SummaryBasis
from app.domain.code.values import CodeKind
from app.domain.forecast.summary import ForecastColumn, ForecastSummary

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.application.ports.clock import Clock
    from app.application.ports.forecast_repository import ForecastCriteria
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.forecast.summary import ForecastRow
    from app.domain.user.value_objects import UserId, UserRef


class GetForecastSummary:
    """Deal 원장에서 지금 시점의 Forecast 요약을 집계한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, criteria: ForecastCriteria) -> ForecastSummaryView:
        async with self._uow_factory() as uow:
            columns = ForecastColumn.from_codes(await uow.codes.list(CodeKind.FORECAST))
            buckets = await uow.forecast.tally(criteria)
            summary = ForecastSummary.build(columns, buckets)
            refs = await uow.users.get_refs(
                [r.owner_id for r in summary.rows if r.owner_id is not None]
            )
        summary = summary.ordered(lambda owner: (refs[owner].resigned, refs[owner].name, owner))
        return ForecastSummaryView(
            basis=SummaryBasis.LIVE,
            as_of=self._clock.now(),
            snapshot_period=None,
            period=criteria.period,
            columns=summary.columns,
            rows=[row_view(r, refs) for r in summary.rows],
            total=ForecastRowView(None, summary.total.cells, summary.total.open_total),
        )


def row_view(row: ForecastRow, refs: Mapping[UserId, UserRef]) -> ForecastRowView:
    owner = refs[row.owner_id] if row.owner_id is not None else None
    return ForecastRowView(owner, row.cells, row.open_total)
