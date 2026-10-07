from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    """현재 시각 Port. 유스케이스가 시스템 시계를 직접 부르지 않게 해 테스트에서 고정할 수 있다."""

    def now(self) -> datetime:
        """시간대 정보가 있는 현재 시각."""
        ...
