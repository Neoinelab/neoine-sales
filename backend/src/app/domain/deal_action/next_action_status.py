"""Next Action 상태: Open, 종료(수행), 종료(미수행). Next Action이 있는 Action에만 있다."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import datetime

_LABELS = {"open": "Open", "done": "종료(수행)", "not_done": "종료(미수행)"}


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


@dataclass(frozen=True, slots=True)
class NextActionState:
    """상태와 종료 시각. open이면 종료 시각이 없고, 종료면 시간대 있는 종료 시각이 있다."""

    status: NextActionStatus
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.status.is_closed:
            if self.closed_at is not None:
                raise InvalidValueError("Open 상태에는 종료 시각이 없어야 합니다.")
            return
        if self.closed_at is None:
            raise InvalidValueError("종료 상태에는 종료 시각이 필요합니다.")
        require_aware(self.closed_at, "closed_at")

    @classmethod
    def open(cls) -> Self:
        return cls(NextActionStatus.OPEN)

    @classmethod
    def of(cls, status: NextActionStatus, now: datetime) -> Self:
        """status로 가는 새 상태. 종료면 종료 시각은 now."""
        return cls(status, now if status.is_closed else None)


@dataclass(frozen=True, slots=True)
class NextActionStatusChange:
    """상태 변경 결과(이력용). note는 trim한 종료 메모(없으면 빈 문자열)."""

    before: NextActionStatus
    after: NextActionStatus
    note: str
