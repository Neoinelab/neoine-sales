from typing import TYPE_CHECKING

from app.application.dashboard.views import (
    AttentionView,
    DashboardView,
    MonthRef,
    QuarterRef,
    StatusItemView,
)
from app.application.deal.views import load_thresholds
from app.domain.code.values import CodeKind
from app.domain.common.business_date import business_date
from app.domain.dashboard.quarter_closing import QuarterClosing
from app.domain.dashboard.status_pipeline import StatusColumn, StatusPipeline
from app.domain.deal.period import quarter_of
from app.domain.deal.risk import RiskBasis
from app.domain.forecast.summary import ForecastColumn, ForecastSummary

if TYPE_CHECKING:
    from app.application.dashboard.criteria import DashboardCriteria
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


class GetDashboardSummary:
    """Deal 원장에서 지금 시점의 Dashboard 요약(Forecast·Status·분기·주의 타일)을 집계한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, criteria: DashboardCriteria) -> DashboardView:
        now = self._clock.now()
        today = business_date(now)
        async with self._uow_factory() as uow:
            stale_days = (await load_thresholds(uow)).stale_days
            forecast_columns = ForecastColumn.from_codes(await uow.codes.list(CodeKind.FORECAST))
            status_columns = StatusColumn.from_codes(await uow.codes.list(CodeKind.STATUS))
            forecast = ForecastSummary.build(
                forecast_columns, await uow.forecast.tally(criteria.forecast_criteria())
            ).total
            statuses = StatusPipeline.build(
                status_columns, await uow.dashboard.tally_by_status(criteria.status_query())
            )
            closing = QuarterClosing.build(
                forecast_columns, await uow.dashboard.tally_by_quarter(criteria.year_query())
            )
            attention = await _attention(uow, criteria, RiskBasis(today, stale_days))
        return DashboardView(
            as_of=now,
            today=today,
            period=criteria.period,
            forecast_columns=closing.columns,
            forecast_cells=forecast.cells,
            open_total=forecast.open_total,
            statuses=[
                StatusItemView(i.column.key, i.column.name, i.column.order, i.tally)
                for i in statuses.items
            ],
            status_total=statuses.total,
            quarters=closing.rows,
            attention=attention,
        )


async def _attention(
    uow: UnitOfWork, criteria: DashboardCriteria, basis: RiskBasis
) -> AttentionView:
    today = basis.today
    month_count = await uow.deals.count(criteria.closing_month_query(today))
    quarter_count = await uow.deals.count(criteria.closing_quarter_query(today))
    return AttentionView(
        stale_days=basis.stale_days,
        overdue=await uow.deals.count(criteria.overdue_query(basis)),
        stale=await uow.deals.count(criteria.stale_query(basis)),
        closing_this_month=MonthRef(today.year, today.month, month_count),
        closing_this_quarter=QuarterRef(today.year, quarter_of(today), quarter_count),
    )
