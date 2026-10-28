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
    query = DealQuery(year=2026, quarters=frozenset({1, 3}))

    assert query.revenue_window() == (date(2026, 1, 1), date(2026, 9, 30))


def test_separated_quarters_are_rechecked_by_revenue_quarters() -> None:
    assert DealQuery(year=2026, quarters=frozenset({1, 3})).revenue_quarters() == frozenset({1, 3})


def test_a_single_quarter_keeps_the_previous_window() -> None:
    query = DealQuery(year=2026, quarters=frozenset({2}))

    assert query.revenue_window() == (date(2026, 4, 1), date(2026, 6, 30))
    assert query.revenue_quarters() == frozenset({2})


@pytest.mark.parametrize("quarters", [frozenset({1, 2, 3, 4}), frozenset()])
def test_all_four_or_no_quarters_mean_no_quarter_condition(quarters: frozenset[int]) -> None:
    query = DealQuery(year=2026, quarters=quarters)

    assert query.quarters is None
    assert query.revenue_quarters() is None
    assert query.revenue_window() == (date(2026, 1, 1), date(2026, 12, 31))


def test_no_quarters_by_default() -> None:
    query = DealQuery(year=2026)

    assert query.quarters is None
    assert query.revenue_quarters() is None


@pytest.mark.parametrize("bad", [frozenset({0}), frozenset({5}), frozenset({1, 7})])
def test_a_quarter_outside_one_to_four_is_rejected(bad: frozenset[int]) -> None:
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        DealQuery(year=2026, quarters=bad)


def test_chosen_quarters_without_a_year_are_filled_with_this_year() -> None:
    filled = DealQuery(quarters=frozenset({1, 3})).with_year_for(date(2026, 10, 19))

    assert (filled.year, filled.quarters) == (2026, frozenset({1, 3}))
    assert filled.revenue_window() == (date(2026, 1, 1), date(2026, 9, 30))


def test_chosen_quarters_without_a_year_are_a_programming_error_for_the_window() -> None:
    with pytest.raises(ValueError, match="연도"):
        DealQuery(quarters=frozenset({1, 3})).revenue_window()


def test_all_four_quarters_without_a_year_leave_the_query_without_a_year() -> None:
    filled = DealQuery(quarters=frozenset({1, 2, 3, 4})).with_year_for(date(2026, 10, 19))

    assert filled.year is None


def test_chosen_quarters_and_month_together_raise_invalid_value() -> None:
    with raises_with(InvalidValueError, "Quarter와 월은 함께 선택할 수 없습니다."):
        DealQuery(year=2026, quarters=frozenset({1, 3}), month=2)


def test_all_four_quarters_with_a_month_are_a_month_only_query() -> None:
    query = DealQuery(year=2026, quarters=frozenset({1, 2, 3, 4}), month=2)

    assert query.revenue_window() == (date(2026, 2, 1), date(2026, 2, 28))
    assert query.quarters is None


def test_a_month_query_has_no_quarter_recheck() -> None:
    assert DealQuery(year=2026, month=2).revenue_quarters() is None
