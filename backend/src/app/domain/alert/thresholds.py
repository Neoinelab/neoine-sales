from dataclasses import dataclass
from typing import Self

from app.domain.common.errors import InvalidValueError

STALE_DAYS_MIN = 1
STALE_DAYS_MAX = 365
STALE_DAYS_DEFAULT = 14
STALE_DAYS_RANGE_MESSAGE = (
    f"미업데이트 기준은 {STALE_DAYS_MIN}~{STALE_DAYS_MAX}일 사이의 정수로 입력하세요."
)


@dataclass(frozen=True, slots=True)
class AlertThresholds:
    """경고 기준. 미업데이트 기준(일)은 1~365의 정수(bool 제외)."""

    stale_days: int

    def __post_init__(self) -> None:
        days = self.stale_days
        if type(days) is not int or not STALE_DAYS_MIN <= days <= STALE_DAYS_MAX:
            raise InvalidValueError(STALE_DAYS_RANGE_MESSAGE)

    @classmethod
    def default(cls) -> Self:
        return cls(stale_days=STALE_DAYS_DEFAULT)
