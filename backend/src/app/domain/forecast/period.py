from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError
from app.domain.deal.period import (
    MONTHS_PER_QUARTER,
    QUARTER_MONTH_EXCLUSIVE,
    month_range,
    normalize_quarters,
    quarter_of,
    quarters_span,
)

if TYPE_CHECKING:
    from datetime import date

YEAR_MIN = 1900
YEAR_MAX = 9999


@dataclass(frozen=True, slots=True)
class ForecastPeriod:
    """revenue_date 분류 기간: 연 단독, 연+분기 집합, 연+월 중 하나(분기와 월은 배타). 양끝 포함."""

    year: int
    quarters: frozenset[int] | None = None  # 정규화됨: None 또는 1~3개
    month: int | None = None

    def __post_init__(self) -> None:
        if not YEAR_MIN <= self.year <= YEAR_MAX:
            raise InvalidValueError(f"연도는 {YEAR_MIN}~{YEAR_MAX} 중에서 입력하세요.")
        object.__setattr__(self, "quarters", normalize_quarters(self.quarters))
        if self.quarters is not None and self.month is not None:
            raise InvalidValueError(QUARTER_MONTH_EXCLUSIVE)
        self.date_range()  # month 범위 검증

    @property
    def single_quarter(self) -> int | None:
        """분기가 정확히 하나면 그 값."""
        if self.quarters is not None and len(self.quarters) == 1:
            return next(iter(self.quarters))
        return None

    def sorted_quarters(self) -> tuple[int, ...]:
        return tuple(sorted(self.quarters)) if self.quarters else ()

    def date_range(self) -> tuple[date, date]:
        """범위의 양끝(분기 집합이면 첫 분기 시작~마지막 분기 끝)."""
        if self.month is not None:
            return month_range(self.year, self.month)
        return quarters_span(self.year, self.quarters)

    def contains(self, day: date) -> bool:
        start, end = self.date_range()
        if not start <= day <= end:
            return False
        return self.quarters is None or quarter_of(day) in self.quarters

    def contains_month(self, year: int, month: int) -> bool:
        """(연, 월) 전체가 기간에 속하는지. 월 단위 스냅숏 셀 판정용."""
        start, end = self.date_range()
        if not (start.year, start.month) <= (year, month) <= (end.year, end.month):
            return False
        return self.quarters is None or (month - 1) // MONTHS_PER_QUARTER + 1 in self.quarters
