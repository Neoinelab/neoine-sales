"""Dashboard 요약 쿼리·응답 스키마. 집계 규칙은 application·domain이 정한다."""

from datetime import date
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.application.dashboard.criteria import DashboardCriteria
from app.domain.deal.period import quarter_range
from app.domain.forecast.period import YEAR_MAX, YEAR_MIN, ForecastPeriod
from app.domain.user.value_objects import UserId
from app.domain.vendor.values import VendorId
from app.web.schemas.common import RequestModel
from app.web.schemas.forecast import CellResponse, ColumnResponse, TallyResponse
from app.web.schemas.ids import QueryId
from app.web.schemas.server_datetime import ServerDateTime

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.dashboard.views import (
        AttentionView,
        DashboardView,
        StatusItemView,
    )
    from app.domain.dashboard.quarter_closing import QuarterClosingRow
    from app.domain.forecast.summary import ForecastColumn, Tally


class DashboardSearchParams(RequestModel):
    """GET /dashboard/summary 쿼리. year 필수, 월 조건은 없다(알 수 없는 파라미터는 422)."""

    year: Annotated[int, Field(ge=YEAR_MIN, le=YEAR_MAX)]
    quarter: Annotated[int | None, Field(ge=1, le=4)] = None
    owner_user_id: QueryId | None = None
    vendor_id: QueryId | None = None

    def to_criteria(self) -> DashboardCriteria:
        return DashboardCriteria(
            period=ForecastPeriod(year=self.year, quarter=self.quarter),
            owner_user_id=None if self.owner_user_id is None else UserId(self.owner_user_id),
            vendor_id=None if self.vendor_id is None else VendorId(self.vendor_id),
        )


class DashboardPeriodResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    year: int
    quarter: int | None
    from_: date = Field(alias="from")
    to: date


class DashboardForecastsResponse(BaseModel):
    columns: list[ColumnResponse]
    cells: list[CellResponse]
    open_total: TallyResponse


class StatusItemResponse(TallyResponse):
    key: str
    name: str
    order: int


class DashboardStatusesResponse(BaseModel):
    items: list[StatusItemResponse]
    total: TallyResponse


class QuarterClosingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    quarter: int
    from_: date = Field(alias="from")
    to: date
    cells: list[CellResponse]
    open_total: TallyResponse
    total: TallyResponse


class MonthRefResponse(BaseModel):
    year: int
    month: int
    count: int


class QuarterRefResponse(BaseModel):
    year: int
    quarter: int
    count: int


class AttentionResponse(BaseModel):
    stale_days: int
    overdue: int
    stale: int
    closing_this_month: MonthRefResponse
    closing_this_quarter: QuarterRefResponse


class DashboardSummaryResponse(BaseModel):
    as_of: ServerDateTime
    today: date
    period: DashboardPeriodResponse
    forecasts: DashboardForecastsResponse
    statuses: DashboardStatusesResponse
    quarters: list[QuarterClosingResponse]
    attention: AttentionResponse

    @classmethod
    def from_view(cls, view: DashboardView) -> DashboardSummaryResponse:
        start, end = view.period.date_range()
        return cls(
            as_of=view.as_of,
            today=view.today,
            period=DashboardPeriodResponse(
                year=view.period.year, quarter=view.period.quarter, from_=start, to=end
            ),
            forecasts=DashboardForecastsResponse(
                columns=[_column(c) for c in view.forecast_columns],
                cells=_cells(view.forecast_columns, view.forecast_cells),
                open_total=_tally(view.open_total),
            ),
            statuses=DashboardStatusesResponse(
                items=[_status(item) for item in view.statuses],
                total=_tally(view.status_total),
            ),
            quarters=[
                _quarter(view.forecast_columns, row, view.period.year) for row in view.quarters
            ],
            attention=_attention(view.attention),
        )


def _tally(tally: Tally) -> TallyResponse:
    return TallyResponse(count=tally.count, amount=tally.amount)


def _column(column: ForecastColumn) -> ColumnResponse:
    return ColumnResponse(
        key=column.key, name=column.name, outcome=column.outcome, order=column.order
    )


def _cells(columns: Sequence[ForecastColumn], cells: Mapping[str, Tally]) -> list[CellResponse]:
    return [
        CellResponse(key=c.key, count=cells[c.key].count, amount=cells[c.key].amount)
        for c in columns
    ]


def _status(item: StatusItemView) -> StatusItemResponse:
    return StatusItemResponse(
        key=item.key,
        name=item.name,
        order=item.order,
        count=item.tally.count,
        amount=item.tally.amount,
    )


def _quarter(
    columns: Sequence[ForecastColumn], row: QuarterClosingRow, year: int
) -> QuarterClosingResponse:
    start, end = quarter_range(year, row.quarter)
    return QuarterClosingResponse(
        quarter=row.quarter,
        from_=start,
        to=end,
        cells=_cells(columns, row.cells),
        open_total=_tally(row.open_total),
        total=_tally(row.total),
    )


def _attention(view: AttentionView) -> AttentionResponse:
    month, quarter = view.closing_this_month, view.closing_this_quarter
    return AttentionResponse(
        stale_days=view.stale_days,
        overdue=view.overdue,
        stale=view.stale,
        closing_this_month=MonthRefResponse(year=month.year, month=month.month, count=month.count),
        closing_this_quarter=QuarterRefResponse(
            year=quarter.year, quarter=quarter.quarter, count=quarter.count
        ),
    )
