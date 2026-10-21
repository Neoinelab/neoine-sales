"""ForecastPeriod(P6 R1 AC-3·7·8): 연 / 연+분기 / 연+월 기간, 양끝 포함, 분기와 월은 배타."""

from datetime import date

import pytest
from app.domain.forecast.errors import QUARTER_MONTH_EXCLUSIVE
from app.domain.forecast.period import ForecastPeriod

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with


def test_year_only_period_covers_whole_year() -> None:
    period = ForecastPeriod(year=2026)

    assert period.date_range() == (date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.parametrize(
    ("quarter", "start", "end"),
    [
        (1, date(2026, 1, 1), date(2026, 3, 31)),
        (2, date(2026, 4, 1), date(2026, 6, 30)),
        (3, date(2026, 7, 1), date(2026, 9, 30)),
        (4, date(2026, 10, 1), date(2026, 12, 31)),
    ],
)
def test_quarter_period_ends_on_quarter_last_day(quarter: int, start: date, end: date) -> None:
    assert ForecastPeriod(year=2026, quarter=quarter).date_range() == (start, end)


@pytest.mark.parametrize(
    ("year", "month", "last_day"),
    [(2026, 1, 31), (2026, 2, 28), (2028, 2, 29), (2026, 4, 30), (2026, 12, 31)],
)
def test_month_period_ends_on_month_last_day(year: int, month: int, last_day: int) -> None:
    period = ForecastPeriod(year=year, month=month)

    assert period.date_range() == (date(year, month, 1), date(year, month, last_day))


def test_december_31_belongs_to_q4_and_jan_1_to_next_year() -> None:
    q4 = ForecastPeriod(year=2026, quarter=4)
    next_q1 = ForecastPeriod(year=2027, quarter=1)
    next_january = ForecastPeriod(year=2027, month=1)

    assert q4.contains(date(2026, 12, 31))
    assert not q4.contains(date(2027, 1, 1))
    assert next_q1.contains(date(2027, 1, 1))
    assert next_january.contains(date(2027, 1, 1))
    assert not next_january.contains(date(2026, 12, 31))


def test_contains_is_inclusive_at_both_ends_and_false_outside() -> None:
    q4 = ForecastPeriod(year=2026, quarter=4)

    assert q4.contains(date(2026, 10, 1))
    assert q4.contains(date(2026, 12, 31))
    assert not q4.contains(date(2026, 9, 30))


def test_quarter_and_month_together_raise_invalid_value() -> None:
    with raises_with(InvalidValueError, QUARTER_MONTH_EXCLUSIVE):
        ForecastPeriod(year=2026, quarter=1, month=1)


def test_the_exclusive_message_is_the_documented_text() -> None:
    assert QUARTER_MONTH_EXCLUSIVE == "Quarter와 월은 함께 선택할 수 없습니다."


@pytest.mark.parametrize("month", [0, 13, -1])
def test_month_out_of_range_raises_invalid_value(month: int) -> None:
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=2026, month=month)


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_out_of_range_raises_invalid_value(quarter: int) -> None:
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=2026, quarter=quarter)


@pytest.mark.parametrize("year", [1899, 10000])
def test_year_out_of_range_raises_invalid_value(year: int) -> None:
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_year_bounds_are_accepted(year: int) -> None:
    assert ForecastPeriod(year=year).date_range()[0] == date(year, 1, 1)
