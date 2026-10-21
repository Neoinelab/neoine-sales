"""최종 업데이트 기간 프리셋. 범위는 서버 업무 날짜 기준이고 오늘을 포함한다."""

import calendar
from datetime import date, timedelta
from enum import StrEnum

TWO_WEEKS_DAYS = 14
MONTHS_PER_YEAR = 12


class UpdatedPeriodPreset(StrEnum):
    """값은 API 키다. 정의 순서가 응답 순서다."""

    TWO_WEEKS = "2w"
    ONE_MONTH = "1m"
    TWO_MONTHS = "2m"
    THREE_MONTHS = "3m"
    SIX_MONTHS = "6m"

    def range_until(self, today: date) -> tuple[date, date]:
        """(시작일, today). 양끝 포함."""
        if self is UpdatedPeriodPreset.TWO_WEEKS:
            return today - timedelta(days=TWO_WEEKS_DAYS), today
        return months_before(today, int(self.value[:-1])), today


def months_before(day: date, months: int) -> date:
    """n개월 전 같은 날. 그 달에 그 날이 없으면 그 달의 말일."""
    if months < 0:
        raise ValueError(f"months는 0 이상이어야 합니다: {months}")
    index = day.year * MONTHS_PER_YEAR + (day.month - 1) - months
    year, month = divmod(index, MONTHS_PER_YEAR)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
