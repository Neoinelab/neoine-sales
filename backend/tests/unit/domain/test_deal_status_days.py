"""Status 체류 일수(R05): 오늘 - 진입일(date). 당일 0, 음수면 0.

진입일은 업무 날짜(date)로 이미 정해져 있어 이 계산에는 시간대 변환이 없다(RK-R10).
"""

from datetime import date

from app.domain.deal.risk import status_days

TODAY = date(2026, 10, 20)


def test_entered_today_is_zero_days() -> None:
    """오늘 진입했으면 0일이다.

    테스트 코드: RK-040
    """
    # when: 오늘 진입한 날짜의 체류 일수를 구한다
    actual = status_days(TODAY, TODAY)
    # then: 0이다
    assert actual == 0


def test_entered_three_days_ago_is_three() -> None:
    """3일 전에 진입했으면 3일이다.

    테스트 코드: RK-040
    """
    # when: 3일 전 진입일의 체류 일수를 구한다
    actual = status_days(date(2026, 10, 17), TODAY)
    # then: 3이다
    assert actual == 3


def test_entered_yesterday_is_one_day() -> None:
    """어제 진입했으면 1일이다(날짜 차이).

    테스트 코드: RK-040
    """
    # when: 어제 진입일의 체류 일수를 구한다
    actual = status_days(date(2026, 10, 19), TODAY)
    # then: 1이다
    assert actual == 1


def test_future_entry_is_zero() -> None:
    """진입일이 미래면 0일이다.

    테스트 코드: RK-040
    """
    # when: 미래 진입일의 체류 일수를 구한다
    actual = status_days(date(2026, 10, 25), TODAY)
    # then: 0이다
    assert actual == 0
