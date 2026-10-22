"""quarter_of(day) (Dashboard AC-7): 날짜가 속한 분기(1~4). 경계일은 분기 첫날·마지막 날이다."""

from datetime import date

import pytest

from app.domain.deal.period import quarter_of, quarter_range


@pytest.mark.parametrize(
    ("day", "quarter"),
    [
        (date(2026, 1, 1), 1),
        (date(2026, 3, 31), 1),
        (date(2026, 4, 1), 2),
        (date(2026, 6, 30), 2),
        (date(2026, 7, 1), 3),
        (date(2026, 9, 30), 3),
        (date(2026, 10, 1), 4),
        (date(2026, 12, 31), 4),
        (date(2027, 1, 1), 1),
    ],
)
def test_quarter_of_returns_quarter_for_boundary_days(day: date, quarter: int) -> None:
    assert quarter_of(day) == quarter


def test_quarter_of_a_leap_day_is_the_first_quarter() -> None:
    assert quarter_of(date(2028, 2, 29)) == 1


@pytest.mark.parametrize("quarter", [1, 2, 3, 4])
def test_every_day_of_a_quarter_range_maps_back_to_that_quarter(quarter: int) -> None:
    start, end = quarter_range(2026, quarter)

    assert quarter_of(start) == quarter
    assert quarter_of(end) == quarter
