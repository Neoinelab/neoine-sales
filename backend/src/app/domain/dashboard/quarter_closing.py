from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.code.values import ForecastOutcome
from app.domain.deal.period import QUARTERS
from app.domain.forecast.summary import Tally, tally_row

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from app.domain.forecast.summary import ForecastColumn


@dataclass(frozen=True, slots=True)
class QuarterBucket:
    """저장소가 돌려주는 (분기, Forecast key) 묶음."""

    quarter: int  # 1~4
    forecast_key: str
    tally: Tally


@dataclass(frozen=True, slots=True)
class QuarterClosingRow:
    quarter: int
    cells: Mapping[str, Tally]  # columns의 모든 key(없으면 ZERO)
    open_total: Tally  # outcome이 open인 셀의 합
    total: Tally  # open_total + Won 셀


@dataclass(frozen=True, slots=True)
class QuarterClosing:
    columns: Sequence[ForecastColumn]  # Lost 제외
    rows: Sequence[QuarterClosingRow]  # 항상 Q1~Q4

    @classmethod
    def build(cls, columns: Iterable[ForecastColumn], buckets: Iterable[QuarterBucket]) -> Self:
        """Lost 열·묶음과 알 수 없는 key를 버린다. 분기가 1~4 밖인 묶음은 ValueError."""
        shown = [c for c in columns if c.outcome is not ForecastOutcome.LOST]
        keys = {c.key for c in shown}
        per_quarter: dict[int, dict[str, Tally]] = defaultdict(dict)
        for bucket in buckets:
            if not 1 <= bucket.quarter <= QUARTERS:
                msg = f"분기는 1~{QUARTERS}여야 합니다: {bucket.quarter}"
                raise ValueError(msg)
            if bucket.forecast_key not in keys:
                continue
            cells = per_quarter[bucket.quarter]
            cells[bucket.forecast_key] = cells.get(bucket.forecast_key, Tally.ZERO).add(
                bucket.tally
            )
        rows = [_row(quarter, shown, per_quarter[quarter]) for quarter in range(1, QUARTERS + 1)]
        return cls(shown, rows)


def _row(
    quarter: int, columns: Sequence[ForecastColumn], raw: Mapping[str, Tally]
) -> QuarterClosingRow:
    cells, open_total = tally_row(columns, raw)
    total = open_total
    for column in columns:
        if column.outcome is ForecastOutcome.WON:
            total = total.add(cells[column.key])
    return QuarterClosingRow(quarter, cells, open_total, total)
