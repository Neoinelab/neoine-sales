"""Status 체류 일수(R05): 오늘 - 진입 업무 날짜. 당일 0, 음수면 0.

날짜는 OS 로컬 시간대의 달력 날짜다. 테스트가 시간대(TZ)를 고정한다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.risk import status_days

if TYPE_CHECKING:
    from collections.abc import Callable

TODAY = date(2026, 10, 20)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def test_entered_today_is_zero_days() -> None:
    """오늘 진입했으면 0일이다.

    테스트 코드: RK-040
    """
    # when: 오늘 진입한 시각의 체류 일수를 구한다
    actual = status_days(datetime(2026, 10, 20, 0, 5, tzinfo=UTC), TODAY)
    # then: 0이다
    assert actual == 0


def test_entered_three_days_ago_is_three() -> None:
    """3일 전에 진입했으면 3일이다.

    테스트 코드: RK-040
    """
    # when: 3일 전 진입 시각의 체류 일수를 구한다
    actual = status_days(datetime(2026, 10, 17, 9, 0, tzinfo=UTC), TODAY)
    # then: 3이다
    assert actual == 3


def test_entered_late_yesterday_is_one_day_even_a_few_minutes_ago() -> None:
    # Seoul 10-19 23:59 = 14:59Z. 오늘 10-20이면 시각 차이는 몇 분이어도 1일이다.
    """어제 밤에 진입했으면 몇 분 전이어도 1일이다.

    테스트 코드: RK-040
    """
    # when: 어제 23:59(서울)에 진입한 시각의 체류 일수를 구한다
    actual = status_days(datetime(2026, 10, 19, 14, 59, tzinfo=UTC), TODAY)
    # then: 1이다
    assert actual == 1


def test_future_entry_is_zero() -> None:
    """진입 시각이 미래면 0일이다.

    테스트 코드: RK-040
    """
    # when: 미래 진입 시각의 체류 일수를 구한다
    actual = status_days(datetime(2026, 10, 25, 9, 0, tzinfo=UTC), TODAY)
    # then: 0이다
    assert actual == 0


def test_entry_date_uses_the_local_calendar_date() -> None:
    # 10-19 15:30Z = Seoul 10-20 00:30 -> 오늘 진입(0일). UTC 날짜라면 1일이 된다.
    """진입 시각은 서버 시간대의 달력 날짜로 바꿔 센다.

    테스트 코드: RK-040
    """
    # when: UTC 10-19 15:30(서울 10-20 00:30) 진입의 체류 일수를 구한다
    actual = status_days(datetime(2026, 10, 19, 15, 30, tzinfo=UTC), TODAY)
    # then: 서울 날짜로 오늘 진입이라 0이다
    assert actual == 0


def test_naive_entry_is_rejected() -> None:
    """시간대 없는 진입 시각은 거절한다.

    테스트 코드: RK-016
    """
    # when·then: 시간대 없는 시각으로 체류 일수를 구한다 → InvalidValueError(시간대)다
    with pytest.raises(InvalidValueError, match="시간대"):
        status_days(datetime(2026, 10, 1, 9, 0), TODAY)
