from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.deal_repository import DealQuery

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from app.domain.forecast.period import ForecastPeriod
    from app.domain.forecast.snapshot import ForecastSnapshot, YearMonth
    from app.domain.forecast.summary import ForecastBucket, Tally
    from app.domain.user.value_objects import UserId
    from app.domain.vendor.values import VendorId


@dataclass(frozen=True, slots=True)
class ForecastCriteria:
    """집계 조건. Deal 목록과 같은 조건으로 바꿀 수 있어 원장과 항상 일치한다."""

    period: ForecastPeriod
    owner_user_id: UserId | None = None
    vendor_id: VendorId | None = None

    def to_deal_query(self) -> DealQuery:
        return DealQuery(
            year=self.period.year,
            quarter=self.period.quarter,
            month=self.period.month,
            owner_user_id=self.owner_user_id,
            vendor_id=self.vendor_id,
        )


@dataclass(frozen=True, slots=True)
class MonthlyBucket:
    """(revenue 연, revenue 월, 담당자, Forecast key) 묶음. 스냅숏 셀의 원천."""

    revenue_year: int
    revenue_month: int
    owner_id: UserId
    forecast_key: str
    tally: Tally


@dataclass(frozen=True, slots=True)
class SnapshotInfo:
    period: YearMonth
    taken_at: datetime


class ForecastTallyRepository(Protocol):
    """Deal 원장에서 바로 읽는 집계(읽기 전용)."""

    async def tally(self, criteria: ForecastCriteria) -> Sequence[ForecastBucket]:
        """조건에 맞는 Deal을 (담당자, Forecast key)로 묶은 건수·금액. Lost도 포함한다.

        금액은 revenue_amount 합(원 단위). 제외 규칙은 도메인(`ForecastSummary.build`)이 정한다.
        """
        ...

    async def tally_by_month(self) -> Sequence[MonthlyBucket]:
        """모든 Deal을 (revenue 연·월, 담당자, Forecast key)로 묶은 건수·금액. Lost도 포함한다."""
        ...


class ForecastSnapshotRepository(Protocol):
    """월말 스냅숏 저장소. 기준 월당 하나만 보관한다."""

    async def lock_period(self, period: YearMonth) -> None:
        """같은 기준 월의 동시 실행을 직렬화한다(트랜잭션이 끝나면 풀린다)."""
        ...

    async def replace(self, snapshot: ForecastSnapshot) -> None:
        """같은 기준 월이 있으면 시각과 셀을 통째로 바꾸고, 없으면 만든다."""
        ...

    async def get(self, period: YearMonth) -> ForecastSnapshot | None: ...

    async def list_periods(self) -> Sequence[SnapshotInfo]:
        """기준 월 최근 순."""
        ...
