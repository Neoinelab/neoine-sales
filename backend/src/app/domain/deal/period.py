"""연/분기 범위(프런트 `period.ts`와 같은 경계). 양끝을 포함한다."""

import calendar
from datetime import date

from app.domain.common.errors import InvalidValueError

QUARTER_MESSAGE = "분기는 1~4 중에서 선택하세요."
QUARTERS = 4
MONTHS_PER_QUARTER = 3


def quarter_range(year: int, quarter: int | None) -> tuple[date, date]:
    """(시작일, 끝일). quarter가 None이면 그 해 전체, 1~4 밖이면 InvalidValueError."""
    if quarter is None:
        return date(year, 1, 1), date(year, 12, 31)
    if not 1 <= quarter <= QUARTERS:
        raise InvalidValueError(QUARTER_MESSAGE)
    first_month = (quarter - 1) * MONTHS_PER_QUARTER + 1
    last_month = first_month + MONTHS_PER_QUARTER - 1
    last_day = calendar.monthrange(year, last_month)[1]
    return date(year, first_month, 1), date(year, last_month, last_day)
