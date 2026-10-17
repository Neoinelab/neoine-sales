"""Deal 경고(Risk)와 Status 체류 일수. 날짜는 OS 로컬 시간대의 업무 날짜 기준이다."""

from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date
from app.domain.deal.sync_state import FORECAST_LOST, FORECAST_WON

if TYPE_CHECKING:
    from datetime import date, datetime


class Risk(StrEnum):
    OVERDUE = "overdue"
    STALE = "stale"
    OVERDUE_STALE = "overdue_stale"


def is_closed_forecast(forecast_key: str) -> bool:
    """Forecast key가 won·lost면 종결(Open Pipeline 아님). key 기준이라 이름 변경과 무관하다."""
    return forecast_key in {FORECAST_WON, FORECAST_LOST}


def compute_risk(
    *,
    forecast_key: str,
    due_date: date | None,
    last_updated_at: datetime,
    today: date,
    stale_days: int,
) -> Risk | None:
    """종결이면 None. overdue는 기한이 오늘보다 앞, stale은 마지막 갱신 후 stale_days 이상 경과."""
    if is_closed_forecast(forecast_key):
        return None
    overdue = due_date is not None and due_date < today
    stale = (today - business_date(last_updated_at)).days >= stale_days
    if overdue and stale:
        return Risk.OVERDUE_STALE
    if overdue:
        return Risk.OVERDUE
    return Risk.STALE if stale else None


def status_days(status_changed_at: datetime, today: date) -> int:
    """현재 Status에 머문 일수(업무 날짜 차이). 음수면 0."""
    return max((today - business_date(status_changed_at)).days, 0)
