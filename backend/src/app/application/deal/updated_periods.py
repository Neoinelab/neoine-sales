from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date
from app.domain.deal.updated_period import UpcomingPeriodPreset, UpdatedPeriodPreset

if TYPE_CHECKING:
    from datetime import date

    from app.application.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UpdatedPeriodRange:
    preset: UpdatedPeriodPreset
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class UpcomingPeriodRange:
    preset: UpcomingPeriodPreset
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class UpdatedPeriodsView:
    today: date
    periods: list[UpdatedPeriodRange]  # UpdatedPeriodPreset 정의 순서
    upcoming: list[UpcomingPeriodRange]  # UpcomingPeriodPreset 정의 순서


class ListUpdatedPeriods:
    """서버 업무 날짜 기준 최종 업데이트·Action 검색 프리셋 범위(과거·향후). DB를 쓰지 않는다."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    async def execute(self) -> UpdatedPeriodsView:
        today = business_date(self._clock.now())
        periods = [UpdatedPeriodRange(p, *p.range_until(today)) for p in UpdatedPeriodPreset]
        upcoming = [UpcomingPeriodRange(p, *p.range_from(today)) for p in UpcomingPeriodPreset]
        return UpdatedPeriodsView(today=today, periods=periods, upcoming=upcoming)
