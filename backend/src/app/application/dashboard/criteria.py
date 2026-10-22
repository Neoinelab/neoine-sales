from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.deal.period import quarter_of

if TYPE_CHECKING:
    from datetime import date

    from app.domain.deal.risk import RiskBasis
    from app.domain.forecast.period import ForecastPeriod
    from app.domain.user.value_objects import UserId
    from app.domain.vendor.values import VendorId


@dataclass(frozen=True, slots=True)
class DashboardCriteria:
    """Dashboard 각 숫자의 조건을 정의하는 단일 출처. Drill-down URL과 1:1로 대응한다."""

    period: ForecastPeriod  # year + 선택 quarter
    owner_user_id: UserId | None = None
    vendor_id: VendorId | None = None

    def __post_init__(self) -> None:
        if self.period.month is not None:
            msg = "Dashboard는 월 단위 기간을 쓰지 않습니다."
            raise ValueError(msg)

    def forecast_criteria(self) -> ForecastCriteria:
        return ForecastCriteria(self.period, self.owner_user_id, self.vendor_id)

    def status_query(self) -> DealQuery:
        return self._period_query(ForecastOutcomeFilter.NOT_LOST)

    def open_query(self) -> DealQuery:
        return self._period_query(ForecastOutcomeFilter.OPEN)

    def year_query(self) -> DealQuery:
        return DealQuery(
            year=self.period.year, owner_user_id=self.owner_user_id, vendor_id=self.vendor_id
        )

    def overdue_query(self, basis: RiskBasis) -> DealQuery:
        return DealQuery(
            owner_user_id=self.owner_user_id,
            vendor_id=self.vendor_id,
            overdue=True,
            risk_basis=basis,
        )

    def stale_query(self, basis: RiskBasis) -> DealQuery:
        return DealQuery(
            owner_user_id=self.owner_user_id,
            vendor_id=self.vendor_id,
            stale=True,
            risk_basis=basis,
        )

    def closing_month_query(self, today: date) -> DealQuery:
        return DealQuery(
            year=today.year,
            month=today.month,
            owner_user_id=self.owner_user_id,
            vendor_id=self.vendor_id,
            forecast_outcome=ForecastOutcomeFilter.OPEN,
        )

    def closing_quarter_query(self, today: date) -> DealQuery:
        return DealQuery(
            year=today.year,
            quarter=quarter_of(today),
            owner_user_id=self.owner_user_id,
            vendor_id=self.vendor_id,
            forecast_outcome=ForecastOutcomeFilter.OPEN,
        )

    def _period_query(self, outcome: ForecastOutcomeFilter) -> DealQuery:
        return DealQuery(
            year=self.period.year,
            quarter=self.period.quarter,
            owner_user_id=self.owner_user_id,
            vendor_id=self.vendor_id,
            forecast_outcome=outcome,
        )
