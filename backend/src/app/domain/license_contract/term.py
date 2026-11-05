"""라이선스 기간 단위와 종료일 계산. 프런트 `licensePeriod.ts`의 `licenseEnd`와 같다."""

import calendar
from datetime import date, timedelta
from enum import StrEnum

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import DATE_CRITERIA_MAX, check_date_in_bounds

MONTHS_PER_YEAR = 12
END_OUT_OF_RANGE = "라이선스 종료일이 허용 범위를 벗어납니다."


class TermUnit(StrEnum):
    MONTH = "month"
    YEAR = "year"


def license_end(start: date, amount: int, unit: TermUnit) -> date:
    """종료일 = 시작일 + 기간 - 1일.

    시작일의 일에서 1을 뺀 값을 (시작 월 + 기간) 달에 두고(그 달에 없으면 말일),
    일이 1이면 그 달 1일의 전날(전달 말일)이다.
    """
    check_date_in_bounds(start, "라이선스 시작일")
    months = amount * MONTHS_PER_YEAR if unit is TermUnit.YEAR else amount
    index = start.year * MONTHS_PER_YEAR + (start.month - 1) + months
    year, month = index // MONTHS_PER_YEAR, index % MONTHS_PER_YEAR + 1
    if year > DATE_CRITERIA_MAX.year:
        raise InvalidValueError(END_OUT_OF_RANGE)
    if start.day > 1:
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, min(start.day - 1, last_day))
    else:
        end = date(year, month, 1) - timedelta(days=1)
    check_date_in_bounds(end, "라이선스 종료일")
    return end
