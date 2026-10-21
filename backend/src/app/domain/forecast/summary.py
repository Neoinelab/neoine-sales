from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self

from app.domain.code.values import CodeKind, ForecastOutcome

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from app.domain.code.entities import Code
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class Tally:
    """건수와 금액(원 단위 정수)."""

    count: int
    amount: int

    ZERO: ClassVar[Tally]  # 클래스 정의 직후에 채운다

    def add(self, other: Tally) -> Tally:
        return Tally(self.count + other.count, self.amount + other.amount)


Tally.ZERO = Tally(0, 0)


@dataclass(frozen=True, slots=True)
class ForecastColumn:
    key: str
    name: str
    outcome: ForecastOutcome
    order: int

    @classmethod
    def from_codes(cls, codes: Iterable[Code]) -> list[ForecastColumn]:
        """Forecast 코드에서 열을 만든다. order 순, Lost 제외."""
        columns = [
            cls(code.key.value, code.name, code.outcome, code.order)
            for code in codes
            if code.kind is CodeKind.FORECAST and code.outcome is not ForecastOutcome.LOST
        ]
        return sorted(columns, key=lambda column: column.order)


@dataclass(frozen=True, slots=True)
class ForecastBucket:
    """저장소가 돌려주는 (담당자, Forecast key) 묶음."""

    owner_id: UserId
    forecast_key: str
    tally: Tally


@dataclass(frozen=True, slots=True)
class ForecastRow:
    owner_id: UserId | None  # 합계 행은 None
    cells: Mapping[str, Tally]  # columns의 모든 key가 있다(없으면 ZERO)
    open_total: Tally  # outcome이 open인 셀의 합(Won·Lost 제외)


@dataclass(frozen=True, slots=True)
class ForecastSummary:
    columns: Sequence[ForecastColumn]
    rows: Sequence[ForecastRow]
    total: ForecastRow

    @classmethod
    def build(cls, columns: Iterable[ForecastColumn], buckets: Iterable[ForecastBucket]) -> Self:
        """Lost 열·묶음과 알 수 없는 key를 버리고 행·합계를 만든다.

        Open·Won 셀이 모두 0인 담당자는 행에서 뺀다. 합계 행은 행의 합이다.
        """
        shown = [column for column in columns if column.outcome is not ForecastOutcome.LOST]
        keys = {column.key for column in shown}
        per_owner: dict[UserId, dict[str, Tally]] = defaultdict(dict)
        for bucket in buckets:
            if bucket.forecast_key not in keys:
                continue
            cells = per_owner[bucket.owner_id]
            cells[bucket.forecast_key] = cells.get(bucket.forecast_key, Tally.ZERO).add(
                bucket.tally
            )
        rows = [_row(owner, shown, cells) for owner, cells in per_owner.items()]
        rows = [row for row in rows if any(c.count for c in row.cells.values())]
        total = _row(None, shown, _sum_cells(shown, rows))
        return cls(shown, rows, total)

    def ordered(self, sort_key: Callable[[UserId], tuple[bool, str, int]]) -> Self:
        """행을 sort_key(담당자) 순으로 정렬한 사본. 합계는 그대로."""
        rows = sorted(self.rows, key=lambda row: sort_key(_owner_of(row)))
        return type(self)(self.columns, rows, self.total)


def _owner_of(row: ForecastRow) -> UserId:
    if row.owner_id is None:
        msg = "담당자 행에는 owner_id가 있어야 합니다"
        raise ValueError(msg)
    return row.owner_id


def _row(
    owner_id: UserId | None, columns: Sequence[ForecastColumn], cells: Mapping[str, Tally]
) -> ForecastRow:
    full = {column.key: cells.get(column.key, Tally.ZERO) for column in columns}
    open_total = Tally.ZERO
    for column in columns:
        if column.outcome is ForecastOutcome.OPEN:
            open_total = open_total.add(full[column.key])
    return ForecastRow(owner_id, full, open_total)


def _sum_cells(columns: Sequence[ForecastColumn], rows: Sequence[ForecastRow]) -> dict[str, Tally]:
    sums = {column.key: Tally.ZERO for column in columns}
    for row in rows:
        for key, cell in row.cells.items():
            sums[key] = sums[key].add(cell)
    return sums
