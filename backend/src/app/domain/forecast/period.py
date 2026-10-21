from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError
from app.domain.deal.period import QUARTER_MONTH_EXCLUSIVE, month_range, quarter_range

if TYPE_CHECKING:
    from datetime import date

YEAR_MIN = 1900
YEAR_MAX = 9999


@dataclass(frozen=True, slots=True)
class ForecastPeriod:
    """revenue_date 분류 기간: 연 단독, 연+분기, 연+월 중 하나(분기와 월은 배타). 양끝 포함."""

    year: int
    quarter: int | None = None
    month: int | None = None

    def __post_init__(self) -> None:
        if not YEAR_MIN <= self.year <= YEAR_MAX:
            raise InvalidValueError(f"연도는 {YEAR_MIN}~{YEAR_MAX} 중에서 입력하세요.")
        if self.quarter is not None and self.month is not None:
            raise InvalidValueError(QUARTER_MONTH_EXCLUSIVE)
        self.date_range()  # quarter·month 범위 검증

    def date_range(self) -> tuple[date, date]:
        if self.month is not None:
            return month_range(self.year, self.month)
        return quarter_range(self.year, self.quarter)

    def contains(self, day: date) -> bool:
        start, end = self.date_range()
        return start <= day <= end
