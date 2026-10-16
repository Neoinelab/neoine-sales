"""연/분기 범위(AC-22b, R-10): 프런트 `period.ts`와 같은 경계. 양끝을 포함한다."""

from datetime import date

import pytest
from app.domain.deal.period import quarter_range

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with


@pytest.mark.parametrize(
    ("quarter", "start", "end"),
    [
        (1, date(2026, 1, 1), date(2026, 3, 31)),
        (2, date(2026, 4, 1), date(2026, 6, 30)),
        (3, date(2026, 7, 1), date(2026, 9, 30)),
        (4, date(2026, 10, 1), date(2026, 12, 31)),
    ],
)
def test_each_quarter_spans_its_three_months(quarter: int, start: date, end: date) -> None:
    assert quarter_range(2026, quarter) == (start, end)


def test_no_quarter_means_the_whole_year() -> None:
    assert quarter_range(2026, None) == (date(2026, 1, 1), date(2026, 12, 31))


def test_the_first_quarter_of_the_next_year_starts_on_january_first() -> None:
    assert quarter_range(2027, 1) == (date(2027, 1, 1), date(2027, 3, 31))


def test_the_second_quarter_of_a_leap_year_is_unaffected_but_the_first_ends_on_march_31() -> None:
    assert quarter_range(2028, 1)[1] == date(2028, 3, 31)


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_a_quarter_outside_one_to_four_is_rejected(quarter: int) -> None:
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        quarter_range(2026, quarter)
