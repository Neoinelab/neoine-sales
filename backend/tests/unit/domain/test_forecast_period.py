"""ForecastPeriod(P6 R1 AC-3·7·8): 연 / 연+분기 / 연+월 기간, 양끝 포함, 분기와 월은 배타."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.forecast.errors import QUARTER_MONTH_EXCLUSIVE
from app.domain.forecast.period import ForecastPeriod
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
    assert ForecastPeriod(year=2026, quarters=frozenset({quarter})).date_range() == (start, end)


@pytest.mark.parametrize(
    ("year", "month", "last_day"),
    [(2026, 1, 31), (2026, 2, 28), (2028, 2, 29), (2026, 4, 30), (2026, 12, 31)],
)
def test_month_period_ends_on_month_last_day(year: int, month: int, last_day: int) -> None:
    period = ForecastPeriod(year=year, month=month)

    assert period.date_range() == (date(year, month, 1), date(year, month, last_day))


def test_december_31_belongs_to_q4_and_jan_1_to_next_year() -> None:
    q4 = ForecastPeriod(year=2026, quarters=frozenset({4}))
    next_q1 = ForecastPeriod(year=2027, quarters=frozenset({1}))
    next_january = ForecastPeriod(year=2027, month=1)

    assert q4.contains(date(2026, 12, 31))
    assert not q4.contains(date(2027, 1, 1))
    assert next_q1.contains(date(2027, 1, 1))
    assert next_january.contains(date(2027, 1, 1))
    assert not next_january.contains(date(2026, 12, 31))


def test_contains_is_inclusive_at_both_ends_and_false_outside() -> None:
    q4 = ForecastPeriod(year=2026, quarters=frozenset({4}))

    assert q4.contains(date(2026, 10, 1))
    assert q4.contains(date(2026, 12, 31))
    assert not q4.contains(date(2026, 9, 30))


def test_quarter_and_month_together_raise_invalid_value() -> None:
    with raises_with(InvalidValueError, QUARTER_MONTH_EXCLUSIVE):
        ForecastPeriod(year=2026, quarters=frozenset({1}), month=1)


def test_the_exclusive_message_is_the_documented_text() -> None:
    assert QUARTER_MONTH_EXCLUSIVE == "Quarter와 월은 함께 선택할 수 없습니다."


@pytest.mark.parametrize("month", [0, 13, -1])
def test_month_out_of_range_raises_invalid_value(month: int) -> None:
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=2026, month=month)


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_out_of_range_raises_invalid_value(quarter: int) -> None:
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=2026, quarters=frozenset({quarter}))


@pytest.mark.parametrize("year", [1899, 10000])
def test_year_out_of_range_raises_invalid_value(year: int) -> None:
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_year_bounds_are_accepted(year: int) -> None:
    assert ForecastPeriod(year=year).date_range()[0] == date(year, 1, 1)


# ---- 분기 집합(Quarter 다중 선택) ----


def test_a_set_of_separated_quarters_spans_first_start_to_last_end() -> None:
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    assert period.date_range() == (date(2026, 1, 1), date(2026, 9, 30))


def test_contains_follows_the_chosen_quarters_not_the_gap_between_them() -> None:
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    assert period.contains(date(2026, 3, 31))
    assert period.contains(date(2026, 7, 1))
    assert not period.contains(date(2026, 4, 1))
    assert not period.contains(date(2026, 6, 30))
    assert not period.contains(date(2026, 10, 1))
    assert not period.contains(date(2025, 12, 31))


def test_single_quarter_and_sorted_quarters_describe_the_selection() -> None:
    several = ForecastPeriod(year=2026, quarters=frozenset({3, 1}))
    one = ForecastPeriod(year=2026, quarters=frozenset({2}))
    none = ForecastPeriod(year=2026)

    assert (several.single_quarter, several.sorted_quarters()) == (None, (1, 3))
    assert (one.single_quarter, one.sorted_quarters()) == (2, (2,))
    assert (none.single_quarter, none.sorted_quarters()) == (None, ())


def test_all_four_quarters_are_normalized_to_no_quarter_condition() -> None:
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 2, 3, 4}))

    assert period.quarters is None
    assert period == ForecastPeriod(year=2026)
    assert period.sorted_quarters() == ()


def test_an_empty_quarter_set_is_normalized_to_no_quarter_condition() -> None:
    assert ForecastPeriod(year=2026, quarters=frozenset()).quarters is None


def test_chosen_quarters_and_month_together_raise_invalid_value() -> None:
    with raises_with(InvalidValueError, QUARTER_MONTH_EXCLUSIVE):
        ForecastPeriod(year=2026, quarters=frozenset({1}), month=2)


def test_all_four_quarters_with_a_month_are_accepted_as_a_month_only_period() -> None:
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 2, 3, 4}), month=5)

    assert period.date_range() == (date(2026, 5, 1), date(2026, 5, 31))


@pytest.mark.parametrize(("month", "expected"), [(1, True), (3, True), (5, False), (8, True)])
def test_contains_month_follows_the_chosen_quarters(month: int, expected: bool) -> None:
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    assert period.contains_month(2026, month) is expected


def test_contains_month_rejects_another_year() -> None:
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    assert not period.contains_month(2025, 2)
    assert not period.contains_month(2027, 2)


def test_contains_month_of_a_year_only_period_accepts_every_month_of_the_year() -> None:
    period = ForecastPeriod(year=2026)

    assert all(period.contains_month(2026, m) for m in range(1, 13))
    assert not period.contains_month(2027, 1)


def test_contains_month_of_a_month_period_accepts_only_that_month() -> None:
    period = ForecastPeriod(year=2026, month=4)

    assert period.contains_month(2026, 4)
    assert not period.contains_month(2026, 5)
