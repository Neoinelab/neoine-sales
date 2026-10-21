"""DealQuery의 month(P6 R1 AC-12): 그 달 범위, 분기와 배타, 월만 있으면 올해를 채운다."""

from datetime import date

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError


def test_month_revenue_window_is_month_range() -> None:
    assert DealQuery(year=2026, month=3).revenue_window() == (date(2026, 3, 1), date(2026, 3, 31))


def test_month_window_in_a_leap_february_ends_on_the_29th() -> None:
    assert DealQuery(year=2028, month=2).revenue_window()[1] == date(2028, 2, 29)


def test_quarter_and_month_together_raise_invalid_value() -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(year=2026, quarter=1, month=1)


@pytest.mark.parametrize("month", [0, 13])
def test_month_out_of_range_raises_invalid_value(month: int) -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(year=2026, month=month)


def test_month_only_query_takes_this_year() -> None:
    query = DealQuery(month=3).with_year_for(date(2027, 8, 1))

    assert (query.year, query.month) == (2027, 3)
    assert query.revenue_window() == (date(2027, 3, 1), date(2027, 3, 31))


def test_month_with_an_explicit_year_keeps_that_year() -> None:
    query = DealQuery(year=2025, month=3).with_year_for(date(2027, 8, 1))

    assert query.year == 2025


def test_month_only_window_without_the_year_filled_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="연도"):
        DealQuery(month=3).revenue_window()


def test_no_month_leaves_quarter_behaviour_unchanged() -> None:
    window = DealQuery(year=2026, quarter=4).revenue_window()

    assert window == (date(2026, 10, 1), date(2026, 12, 31))
