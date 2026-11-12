"""DealQuery의 month: 그 달 범위, 분기와 배타, 월만 있으면 올해를 채운다."""

from datetime import date

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError


def test_month_revenue_window_is_month_range() -> None:
    """월을 지정하면 매출 기간은 그 달 1일부터 말일까지다."""
    # when: 2026년 3월로 매출 기간을 계산한다
    window = DealQuery(year=2026, month=3).revenue_window()

    # then: 3월 1일~31일이다
    assert window == (date(2026, 3, 1), date(2026, 3, 31))


def test_month_window_in_a_leap_february_ends_on_the_29th() -> None:
    """윤년 2월의 기간은 29일에 끝난다."""
    # when: 2028년 2월로 매출 기간을 계산한다
    window = DealQuery(year=2028, month=2).revenue_window()

    # then: 끝은 2월 29일이다
    assert window[1] == date(2028, 2, 29)


def test_quarter_and_month_together_raise_invalid_value() -> None:
    """분기와 월을 함께 지정하면 InvalidValueError다."""
    # when·then: 분기와 월을 같이 주면 거부한다
    with pytest.raises(InvalidValueError):
        DealQuery(year=2026, quarters=frozenset({1}), month=1)


@pytest.mark.parametrize("month", [0, 13])
def test_month_out_of_range_raises_invalid_value(month: int) -> None:
    """월이 1~12 밖이면 InvalidValueError다."""
    # when·then: 범위 밖 월을 주면 거부한다
    with pytest.raises(InvalidValueError):
        DealQuery(year=2026, month=month)


def test_month_only_query_takes_this_year() -> None:
    """월만 있는 조회는 기준일의 연도를 채운다."""
    # when: 2027-08-01 기준으로 연도를 채운다
    query = DealQuery(month=3).with_year_for(date(2027, 8, 1))

    # then: 2027년 3월 범위가 된다
    assert (query.year, query.month) == (2027, 3)
    assert query.revenue_window() == (date(2027, 3, 1), date(2027, 3, 31))


def test_month_with_an_explicit_year_keeps_that_year() -> None:
    """연도를 명시한 월 조회는 그 연도를 유지한다."""
    # when: 2025년 3월 조회에 다른 해 기준일로 연도를 채운다
    query = DealQuery(year=2025, month=3).with_year_for(date(2027, 8, 1))

    # then: 연도는 2025다
    assert query.year == 2025


def test_month_only_window_without_the_year_filled_is_a_programming_error() -> None:
    """연도를 채우지 않은 월만의 기간 계산은 프로그래밍 오류다."""
    # when·then: 연도 없이 기간을 계산하면 ValueError다
    with pytest.raises(ValueError, match="연도"):
        DealQuery(month=3).revenue_window()


def test_no_month_leaves_quarter_behaviour_unchanged() -> None:
    """월이 없으면 분기 조회 동작은 그대로다."""
    # when: 4분기로 매출 기간을 계산한다
    window = DealQuery(year=2026, quarters=frozenset({4})).revenue_window()

    # then: 10월 1일~12월 31일이다
    assert window == (date(2026, 10, 1), date(2026, 12, 31))
