"""업무 날짜 계산. Deal code의 날짜는 서버 프로세스(OS) 로컬 시간대의 달력 날짜다."""

from datetime import datetime, time
from typing import TYPE_CHECKING

from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import date


def business_date(now: datetime) -> date:
    """시각을 OS 로컬 시간대로 바꾼 달력 날짜. 시간대 정보가 없는 시각은 거절한다."""
    return require_aware(now, "now").astimezone().date()


def start_of_business_day(day: date) -> datetime:
    """업무 날짜의 시작 순간(OS 로컬 00:00, 시간대 정보 있음)."""
    return datetime.combine(day, time.min).astimezone()
