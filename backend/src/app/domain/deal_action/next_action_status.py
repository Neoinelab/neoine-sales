"""Next Action 상태: Open, 종료(수행), 종료(미수행). Next Action이 있는 Action에만 있다."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from app.domain.common.business_date import business_date
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from datetime import date, datetime

_LABELS = {"open": "Open", "done": "종료(수행)", "not_done": "종료(미수행)"}
_SORT_RANKS = {"open": 0, "done": 1, "not_done": 2}


class NextActionStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    NOT_DONE = "not_done"

    @property
    def is_closed(self) -> bool:
        return self is not NextActionStatus.OPEN

    @property
    def label(self) -> str:
        return _LABELS[self.value]

    @property
    def sort_rank(self) -> int:
        """정렬 순위: open 0, done 1, not_done 2(상태 정렬 asc 순서)."""
        return _SORT_RANKS[self.value]


@dataclass(frozen=True, slots=True)
class NextActionState:
    """상태와 종료일. open이면 종료일이 없고, 종료면 종료일(업무 날짜)이 있다."""

    status: NextActionStatus
    closed_on: date | None = None

    def __post_init__(self) -> None:
        if not self.status.is_closed:
            if self.closed_on is not None:
                raise InvalidValueError("Open 상태에는 종료일이 없어야 합니다.")
            return
        if self.closed_on is None:
            raise InvalidValueError("종료 상태에는 종료일이 필요합니다.")

    @classmethod
    def open(cls) -> Self:
        return cls(NextActionStatus.OPEN)

    @classmethod
    def of(cls, status: NextActionStatus, now: datetime) -> Self:
        """status로 가는 새 상태. 종료면 종료일은 now의 업무 날짜."""
        return cls(status, business_date(now) if status.is_closed else None)


@dataclass(frozen=True, slots=True)
class NextActionStatusChange:
    """상태 변경 결과(이력용). note는 trim한 종료 Comment(없으면 빈 문자열)."""

    before: NextActionStatus
    after: NextActionStatus
    note: str
