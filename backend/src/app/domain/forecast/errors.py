"""Forecast 도메인 오류. 분기·월 배타 메시지의 정본은 `app.domain.deal.period`."""

from app.domain.common.errors import InvalidValueError, NotFoundError
from app.domain.deal.period import QUARTER_MONTH_EXCLUSIVE

__all__ = [
    "QUARTER_MONTH_EXCLUSIVE",
    "ForecastSnapshotNotFoundError",
    "SnapshotMonthNotAllowedError",
]


class SnapshotMonthNotAllowedError(InvalidValueError):
    """다시 계산할 수 없는 기준 월(전월·당월이 아님)."""


class ForecastSnapshotNotFoundError(NotFoundError):
    def __init__(self, period: object) -> None:
        super().__init__("스냅숏", period, message=f"해당 기준 월의 스냅숏이 없습니다: {period}")
