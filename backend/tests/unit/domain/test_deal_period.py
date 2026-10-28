"""연/분기 범위(AC-22b, R-10): 프런트 `period.ts`와 같은 경계. 양끝을 포함한다."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.period import normalize_quarters, quarter_range, quarters_span
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


# ---- 분기 집합(Quarter 다중 선택) ----


@pytest.mark.parametrize(
    "raw",
    [None, [], set(), frozenset(), [1, 2, 3, 4], {4, 3, 2, 1}, [1, 2, 3, 4, 4]],
    ids=["none", "empty-list", "empty-set", "empty-frozenset", "all", "all-unordered", "all-dup"],
)
def test_no_quarter_and_all_four_quarters_both_mean_no_condition(raw: object) -> None:
    assert normalize_quarters(raw) is None  # type: ignore[arg-type]


def test_normalize_quarters_drops_duplicates_and_keeps_a_frozenset() -> None:
    assert normalize_quarters([3, 1, 1]) == frozenset({1, 3})


def test_normalize_quarters_keeps_a_single_quarter() -> None:
    assert normalize_quarters({2}) == frozenset({2})


@pytest.mark.parametrize("bad", [[0], [5], [1, 5], [-1, 2]])
def test_normalize_quarters_rejects_a_value_outside_one_to_four(bad: list[int]) -> None:
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        normalize_quarters(bad)


def test_quarters_span_runs_from_the_first_quarter_start_to_the_last_quarter_end() -> None:
    assert quarters_span(2026, frozenset({1, 3})) == (date(2026, 1, 1), date(2026, 9, 30))


def test_quarters_span_of_one_quarter_is_that_quarter() -> None:
    assert quarters_span(2026, frozenset({4})) == (date(2026, 10, 1), date(2026, 12, 31))


def test_quarters_span_without_quarters_is_the_whole_year() -> None:
    assert quarters_span(2026, None) == (date(2026, 1, 1), date(2026, 12, 31))
