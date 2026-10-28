"""Forecast 요약 쿼리·응답 스키마. 기간 조합(Quarter와 월 배타)은 도메인이 판정한다."""

from datetime import date
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.application.forecast.views import ForecastRowView, ForecastSummaryView, SummaryBasis
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.code.values import ForecastOutcome
from app.domain.forecast.period import YEAR_MAX, YEAR_MIN, ForecastPeriod
from app.domain.user.value_objects import UserId
from app.domain.vendor.values import VendorId
from app.web.schemas.common import RequestModel
from app.web.schemas.ids import QueryId
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.forecast_repository import SnapshotInfo
    from app.domain.forecast.summary import ForecastColumn, Tally


class ForecastSnapshotSearchParams(RequestModel):
    """GET /forecast/snapshots/{period}/summary 쿼리. 실시간 요약과 같되 Vendor 조건은 없다."""

    year: Annotated[int, Field(ge=YEAR_MIN, le=YEAR_MAX)]
    quarter: Annotated[int | None, Field(ge=1, le=4)] = None
    month: Annotated[int | None, Field(ge=1, le=12)] = None
    owner_user_id: QueryId | None = None

    def _quarters(self) -> frozenset[int] | None:
        return None if self.quarter is None else frozenset({self.quarter})

    def to_criteria(self) -> ForecastCriteria:
        return ForecastCriteria(
            period=ForecastPeriod(year=self.year, quarters=self._quarters(), month=self.month),
            owner_user_id=None if self.owner_user_id is None else UserId(self.owner_user_id),
            vendor_id=None,
        )


class ForecastSearchParams(ForecastSnapshotSearchParams):
    """GET /forecast/summary 쿼리. year 필수, quarter·month는 함께 쓸 수 없다(도메인이 거절)."""

    vendor_id: QueryId | None = None

    def to_criteria(self) -> ForecastCriteria:
        return ForecastCriteria(
            period=ForecastPeriod(year=self.year, quarters=self._quarters(), month=self.month),
            owner_user_id=None if self.owner_user_id is None else UserId(self.owner_user_id),
            vendor_id=None if self.vendor_id is None else VendorId(self.vendor_id),
        )


class SnapshotItemResponse(BaseModel):
    period: str
    taken_at: ServerDateTime


class SnapshotListResponse(BaseModel):
    items: list[SnapshotItemResponse]

    @classmethod
    def from_infos(cls, infos: Sequence[SnapshotInfo]) -> SnapshotListResponse:
        return cls(
            items=[SnapshotItemResponse(period=str(i.period), taken_at=i.taken_at) for i in infos]
        )


class TallyResponse(BaseModel):
    count: int
    amount: int


class CellResponse(TallyResponse):
    key: str


class ColumnResponse(BaseModel):
    key: str
    name: str
    outcome: ForecastOutcome
    order: int


class PeriodResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    year: int
    quarter: int | None
    month: int | None
    from_: date = Field(alias="from")
    to: date


class RowResponse(BaseModel):
    owner: UserRef | None
    cells: list[CellResponse]
    open_total: TallyResponse


class ForecastSummaryResponse(BaseModel):
    basis: SummaryBasis
    as_of: ServerDateTime
    snapshot_period: str | None
    period: PeriodResponse
    columns: list[ColumnResponse]
    rows: list[RowResponse]
    total: RowResponse

    @classmethod
    def from_view(cls, view: ForecastSummaryView) -> ForecastSummaryResponse:
        keys = [column.key for column in view.columns]
        start, end = view.period.date_range()
        return cls(
            basis=view.basis,
            as_of=view.as_of,
            snapshot_period=view.snapshot_period,
            period=PeriodResponse(
                year=view.period.year,
                quarter=view.period.single_quarter,
                month=view.period.month,
                from_=start,
                to=end,
            ),
            columns=[_column(column) for column in view.columns],
            rows=[_row(row, keys) for row in view.rows],
            total=_row(view.total, keys),
        )


def _tally(tally: Tally) -> TallyResponse:
    return TallyResponse(count=tally.count, amount=tally.amount)


def _column(column: ForecastColumn) -> ColumnResponse:
    return ColumnResponse(
        key=column.key, name=column.name, outcome=column.outcome, order=column.order
    )


def _row(row: ForecastRowView, keys: list[str]) -> RowResponse:
    return RowResponse(
        owner=None if row.owner is None else UserRef.from_domain(row.owner),
        cells=[
            CellResponse(key=key, count=row.cells[key].count, amount=row.cells[key].amount)
            for key in keys
        ],
        open_total=_tally(row.open_total),
    )
