"""Deal 경고(Risk)와 Status 체류 일수. 날짜는 OS 로컬 시간대의 업무 날짜 기준이다."""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.domain.deal.sync_state import CLOSED_FORECASTS


class Risk(StrEnum):
    OVERDUE = "overdue"
    STALE = "stale"
    OVERDUE_STALE = "overdue_stale"


def is_closed_forecast(forecast_key: str) -> bool:
    """Forecast key가 won·lost면 종결(Open Pipeline 아님). key 기준이라 이름 변경과 무관하다."""
    return forecast_key in CLOSED_FORECASTS


def compute_risk(
    *,
    forecast_key: str,
    earliest_open_due: date | None,
    last_updated_on: date,
    today: date,
    stale_days: int,
) -> Risk | None:
    """종결이면 None. overdue는 Open Next Action의 가장 이른 Due < 오늘.

    stale은 마지막 갱신 후 stale_days 이상 경과.
    """
    if is_closed_forecast(forecast_key):
        return None
    overdue = earliest_open_due is not None and earliest_open_due < today
    stale = (today - last_updated_on).days >= stale_days
    if overdue and stale:
        return Risk.OVERDUE_STALE
    if overdue:
        return Risk.OVERDUE
    return Risk.STALE if stale else None


@dataclass(frozen=True, slots=True)
class RiskBasis:
    """목록 위험 필터의 기준: 오늘(업무 날짜)과 미업데이트 기준 일수. compute_risk와 같은 판정."""

    today: date
    stale_days: int

    def __post_init__(self) -> None:
        if self.stale_days < 1:
            raise ValueError("stale_days는 1 이상이어야 합니다.")

    def stale_before(self) -> date:
        """last_updated_on < 이 날짜이면 미업데이트.

        (today - d).days >= stale_days <=> d <= today - stale_days <=> d < today - (stale_days - 1)
        """
        return self.today - timedelta(days=self.stale_days - 1)


def status_days(status_changed_on: date, today: date) -> int:
    """현재 Status에 머문 일수(날짜 차이). 음수면 0."""
    return max((today - status_changed_on).days, 0)
