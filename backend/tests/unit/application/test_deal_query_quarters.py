"""DealQuery의 분기 집합(Quarter 다중 선택): 정규화, 범위 양끝, 분기 재검사, 월과의 배타.

`revenue_window()`는 고른 분기의 첫 시작~마지막 끝(사이 분기를 포함하는 범위)이므로, 떨어진 분기는
`revenue_quarters()`와 AND로 써야 한다.
"""

from datetime import date

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with


def test_separated_quarters_have_a_window_from_first_start_to_last_end() -> None:
    """떨어진 분기는 첫 분기 시작부터 마지막 분기 끝까지의 범위가 된다."""
    # given: 1분기와 3분기를 고른 조회 조건
    query = DealQuery(year=2026, quarters=frozenset({1, 3}))

    # when: Expected Close 범위를 구한다
    window = query.revenue_window()

    # then: 1월 1일부터 9월 30일이다
    assert window == (date(2026, 1, 1), date(2026, 9, 30))


def test_separated_quarters_are_rechecked_by_revenue_quarters() -> None:
    """떨어진 분기는 고른 분기 집합으로 다시 검사한다."""
    # given: 1분기와 3분기를 고른 조회 조건
    query = DealQuery(year=2026, quarters=frozenset({1, 3}))

    # when: 재검사할 분기를 구한다
    rechecked = query.revenue_quarters()

    # then: 고른 분기 그대로다
    assert rechecked == frozenset({1, 3})


def test_a_single_quarter_keeps_the_previous_window() -> None:
    """분기 하나만 고르면 그 분기의 범위가 된다."""
    # given: 2분기만 고른 조회 조건
    query = DealQuery(year=2026, quarters=frozenset({2}))

    # when: 범위와 재검사 분기를 구한다
    window = query.revenue_window()
    rechecked = query.revenue_quarters()

    # then: 4월 1일~6월 30일이고 재검사 분기는 2분기다
    assert window == (date(2026, 4, 1), date(2026, 6, 30))
    assert rechecked == frozenset({2})


@pytest.mark.parametrize("quarters", [frozenset({1, 2, 3, 4}), frozenset()])
def test_all_four_or_no_quarters_mean_no_quarter_condition(quarters: frozenset[int]) -> None:
    """네 분기를 모두 고르거나 아무것도 고르지 않으면 분기 조건이 없다."""
    # when: 네 분기 전부 또는 빈 집합으로 조회 조건을 만든다
    query = DealQuery(year=2026, quarters=quarters)

    # then: 분기 조건이 없고 범위는 한 해 전체다
    assert query.quarters is None
    assert query.revenue_quarters() is None
    assert query.revenue_window() == (date(2026, 1, 1), date(2026, 12, 31))


def test_no_quarters_by_default() -> None:
    """분기를 주지 않으면 분기 조건이 없다."""
    # when: 분기 없이 조회 조건을 만든다
    query = DealQuery(year=2026)

    # then: 분기 조건이 없다
    assert query.quarters is None
    assert query.revenue_quarters() is None


@pytest.mark.parametrize("bad", [frozenset({0}), frozenset({5}), frozenset({1, 7})])
def test_a_quarter_outside_one_to_four_is_rejected(bad: frozenset[int]) -> None:
    """1~4 밖의 분기는 거절한다."""
    # when·then: 범위 밖 분기로 조회 조건을 만들면 값 오류다
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        DealQuery(year=2026, quarters=bad)


def test_chosen_quarters_without_a_year_are_filled_with_this_year() -> None:
    """연도 없이 분기를 고르면 올해로 채운다."""
    # given: 연도 없이 1·3분기를 고른 조회 조건
    query = DealQuery(quarters=frozenset({1, 3}))

    # when: 오늘 날짜(2026-10-19) 기준으로 연도를 채운다
    filled = query.with_year_for(date(2026, 10, 19))

    # then: 연도는 2026이고 분기와 범위가 유지된다
    assert (filled.year, filled.quarters) == (2026, frozenset({1, 3}))
    assert filled.revenue_window() == (date(2026, 1, 1), date(2026, 9, 30))


def test_chosen_quarters_without_a_year_are_a_programming_error_for_the_window() -> None:
    """연도 없는 분기 조건으로 범위를 구하면 프로그래밍 오류다."""
    # given: 연도 없이 1·3분기를 고른 조회 조건
    query = DealQuery(quarters=frozenset({1, 3}))

    # when·then: 범위를 구하면 연도 관련 ValueError다
    with pytest.raises(ValueError, match="연도"):
        query.revenue_window()


def test_all_four_quarters_without_a_year_leave_the_query_without_a_year() -> None:
    """네 분기 전체를 고르면 연도를 채우지 않는다."""
    # given: 연도 없이 네 분기를 모두 고른 조회 조건
    query = DealQuery(quarters=frozenset({1, 2, 3, 4}))

    # when: 오늘 날짜 기준으로 연도를 채운다
    filled = query.with_year_for(date(2026, 10, 19))

    # then: 연도는 비어 있다
    assert filled.year is None


def test_chosen_quarters_and_month_together_raise_invalid_value() -> None:
    """분기와 월을 함께 고르면 값 오류다."""
    # when·then: 1·3분기와 2월을 함께 주면 값 오류다
    with raises_with(InvalidValueError, "Quarter와 월은 함께 선택할 수 없습니다."):
        DealQuery(year=2026, quarters=frozenset({1, 3}), month=2)


def test_all_four_quarters_with_a_month_are_a_month_only_query() -> None:
    """네 분기 전체와 월을 함께 주면 월만 있는 조회가 된다."""
    # when: 네 분기 전체와 2월로 조회 조건을 만든다
    query = DealQuery(year=2026, quarters=frozenset({1, 2, 3, 4}), month=2)

    # then: 범위는 2월 한 달이고 분기 조건은 없다
    assert query.revenue_window() == (date(2026, 2, 1), date(2026, 2, 28))
    assert query.quarters is None


def test_a_month_query_has_no_quarter_recheck() -> None:
    """월 조회는 분기 재검사가 없다."""
    # given: 2월만 고른 조회 조건
    query = DealQuery(year=2026, month=2)

    # when: 재검사할 분기를 구한다
    rechecked = query.revenue_quarters()

    # then: 없다
    assert rechecked is None
