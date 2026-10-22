from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.code.values import CodeKind
from app.domain.forecast.summary import Tally

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from app.domain.code.entities import Code


@dataclass(frozen=True, slots=True)
class StatusColumn:
    key: str
    name: str
    order: int

    @classmethod
    def from_codes(cls, codes: Iterable[Code]) -> list[StatusColumn]:
        """Status 코드만, order 순."""
        columns = [
            cls(code.key.value, code.name, code.order)
            for code in codes
            if code.kind is CodeKind.STATUS
        ]
        return sorted(columns, key=lambda column: column.order)


@dataclass(frozen=True, slots=True)
class StatusItem:
    column: StatusColumn
    tally: Tally


@dataclass(frozen=True, slots=True)
class StatusPipeline:
    items: Sequence[StatusItem]  # 모든 Status 코드, 입력 순서, Deal 없으면 ZERO
    total: Tally  # items의 합

    @classmethod
    def build(cls, columns: Iterable[StatusColumn], tallies: Mapping[str, Tally]) -> Self:
        """알 수 없는 key의 묶음은 버린다(코드 FK가 있어 정상 데이터에는 없다)."""
        items = [StatusItem(column, tallies.get(column.key, Tally.ZERO)) for column in columns]
        total = Tally.ZERO
        for item in items:
            total = total.add(item.tally)
        return cls(items, total)
