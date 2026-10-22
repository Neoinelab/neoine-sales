from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date, datetime

    from app.domain.dashboard.quarter_closing import QuarterClosingRow
    from app.domain.forecast.period import ForecastPeriod
    from app.domain.forecast.summary import ForecastColumn, Tally


@dataclass(frozen=True, slots=True)
class StatusItemView:
    key: str
    name: str
    order: int
    tally: Tally


@dataclass(frozen=True, slots=True)
class MonthRef:
    year: int
    month: int
    count: int


@dataclass(frozen=True, slots=True)
class QuarterRef:
    year: int
    quarter: int
    count: int


@dataclass(frozen=True, slots=True)
class AttentionView:
    stale_days: int
    overdue: int
    stale: int
    closing_this_month: MonthRef
    closing_this_quarter: QuarterRef


@dataclass(frozen=True, slots=True)
class DashboardView:
    as_of: datetime
    today: date
    period: ForecastPeriod
    forecast_columns: Sequence[ForecastColumn]  # Lost 제외
    forecast_cells: Mapping[str, Tally]
    open_total: Tally
    statuses: Sequence[StatusItemView]
    status_total: Tally
    quarters: Sequence[QuarterClosingRow]  # Q1~Q4
    attention: AttentionView
