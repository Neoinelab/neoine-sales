from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from app.domain.code.values import ForecastOutcome
from app.domain.common.errors import InvalidValueError
from app.domain.forecast.errors import SnapshotMonthNotAllowedError
from app.domain.forecast.summary import ForecastBucket, ForecastColumn, ForecastSummary

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date, datetime

    from app.domain.forecast.period import ForecastPeriod
    from app.domain.forecast.summary import Tally
    from app.domain.user.value_objects import UserId

_MONTHS_PER_YEAR = 12


@dataclass(frozen=True, slots=True, order=True)
class YearMonth:
    """스냅숏 기준 월. 텍스트 형식은 `YYYY-MM` 하나뿐이다."""

    year: int
    month: int

    _FORMAT: ClassVar[str] = "YYYY-MM"

    def __post_init__(self) -> None:
        if not 1 <= self.month <= _MONTHS_PER_YEAR or not 1 <= self.year <= 9999:  # noqa: PLR2004
            raise InvalidValueError("기준 월은 YYYY-MM 형식이어야 합니다.")

    @classmethod
    def parse(cls, text: str) -> YearMonth:
        ok = (
            len(text) == 7  # noqa: PLR2004
            and text[4] == "-"
            and all(c in "0123456789" for c in text[:4] + text[5:])
        )
        if not ok:
            raise InvalidValueError("기준 월은 YYYY-MM 형식이어야 합니다.")
        return cls(int(text[:4]), int(text[5:]))

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def previous(self) -> YearMonth:
        if self.month == 1:
            return YearMonth(self.year - 1, _MONTHS_PER_YEAR)
        return YearMonth(self.year, self.month - 1)

    @classmethod
    def of(cls, day: date) -> YearMonth:
        return cls(day.year, day.month)


def default_snapshot_month(today: date) -> YearMonth:
    """기본 기준 월: 실행일의 전월."""
    return YearMonth.of(today).previous()


def ensure_snapshot_allowed(target: YearMonth, today: date) -> None:
    """전월·당월만 다시 계산할 수 있다(그 이전·미래는 거부)."""
    current = YearMonth.of(today)
    if target not in (current, current.previous()):
        raise SnapshotMonthNotAllowedError(
            f"{target} 기준 월은 다시 계산할 수 없습니다. 전월과 당월만 가능합니다."
        )


@dataclass(frozen=True, slots=True)
class SnapshotColumn:
    """스냅숏을 만든 시점의 Forecast 코드 하나(키·이름·분류·순서)."""

    key: str
    name: str
    outcome: ForecastOutcome
    order: int


@dataclass(frozen=True, slots=True)
class SnapshotCell:
    """(revenue 연·월, 담당자, Forecast key) 묶음 하나. Deal이 있는 칸만 저장한다."""

    revenue_year: int
    revenue_month: int
    owner_id: UserId
    forecast_key: str
    tally: Tally


@dataclass(frozen=True, slots=True)
class ForecastSnapshot:
    period: YearMonth
    taken_at: datetime
    columns: Sequence[SnapshotColumn]
    cells: Sequence[SnapshotCell]

    def summary(self, period: ForecastPeriod, owner_id: UserId | None) -> ForecastSummary:
        """기간·담당자로 셀을 모아 실시간과 같은 규칙으로 요약한다. 열은 저장한 코드 목록이다."""
        shown = sorted(
            (c for c in self.columns if c.outcome is not ForecastOutcome.LOST),
            key=lambda column: column.order,
        )
        columns = [ForecastColumn(c.key, c.name, c.outcome, c.order) for c in shown]
        buckets = [
            ForecastBucket(cell.owner_id, cell.forecast_key, cell.tally)
            for cell in self.cells
            if _in_period(cell, period) and (owner_id is None or cell.owner_id == owner_id)
        ]
        return ForecastSummary.build(columns, buckets)


def _in_period(cell: SnapshotCell, period: ForecastPeriod) -> bool:
    return period.contains_month(cell.revenue_year, cell.revenue_month)
