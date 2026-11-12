"""연/분기 범위(R-10): 프런트 `period.ts`와 같은 경계. 양끝을 포함한다."""

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
    """각 분기가 해당 세 달의 처음과 끝으로 풀리는지 확인한다."""
    # when: 분기 범위를 구한다
    result = quarter_range(2026, quarter)
    # then: 시작일과 종료일이 분기 경계 날짜다
    assert result == (start, end)


def test_no_quarter_means_the_whole_year() -> None:
    """분기를 주지 않으면 한 해 전체인지 확인한다."""
    # when: 분기 없이 범위를 구한다
    result = quarter_range(2026, None)
    # then: 1월 1일부터 12월 31일이다
    assert result == (date(2026, 1, 1), date(2026, 12, 31))


def test_the_first_quarter_of_the_next_year_starts_on_january_first() -> None:
    """다음 해 1분기가 1월 1일에 시작하는지 확인한다."""
    # when: 2027년 1분기 범위를 구한다
    result = quarter_range(2027, 1)
    # then: 1월 1일~3월 31일이다
    assert result == (date(2027, 1, 1), date(2027, 3, 31))


def test_the_second_quarter_of_a_leap_year_is_unaffected_but_the_first_ends_on_march_31() -> None:
    """윤년의 1분기도 3월 31일에 끝나는지 확인한다."""
    # when: 2028년 1분기 범위를 구한다
    result = quarter_range(2028, 1)[1]
    # then: 종료일이 3월 31일이다
    assert result == date(2028, 3, 31)


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_a_quarter_outside_one_to_four_is_rejected(quarter: int) -> None:
    """1~4 밖의 분기는 거절하는지 확인한다."""
    # when·then: 범위 밖 분기로 범위를 구하면 분기 선택 오류가 난다
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        quarter_range(2026, quarter)


# ---- 분기 집합(Quarter 다중 선택) ----


@pytest.mark.parametrize(
    "raw",
    [None, [], set(), frozenset(), [1, 2, 3, 4], {4, 3, 2, 1}, [1, 2, 3, 4, 4]],
    ids=["none", "empty-list", "empty-set", "empty-frozenset", "all", "all-unordered", "all-dup"],
)
def test_no_quarter_and_all_four_quarters_both_mean_no_condition(raw: object) -> None:
    """분기가 없거나 네 개 모두면 조건 없음(None)인지 확인한다."""
    # when: 정규화한다
    result = normalize_quarters(raw)  # type: ignore[arg-type]
    # then: None이다
    assert result is None


def test_normalize_quarters_drops_duplicates_and_keeps_a_frozenset() -> None:
    """중복 분기를 없애고 frozenset으로 돌려주는지 확인한다."""
    # when: 중복이 있는 분기를 정규화한다
    result = normalize_quarters([3, 1, 1])
    # then: 중복 없는 frozenset이다
    assert result == frozenset({1, 3})


def test_normalize_quarters_keeps_a_single_quarter() -> None:
    """분기 하나만 고르면 그대로 유지하는지 확인한다."""
    # when: 분기 하나를 정규화한다
    result = normalize_quarters({2})
    # then: 그 분기만 든 frozenset이다
    assert result == frozenset({2})


@pytest.mark.parametrize("bad", [[0], [5], [1, 5], [-1, 2]])
def test_normalize_quarters_rejects_a_value_outside_one_to_four(bad: list[int]) -> None:
    """1~4 밖의 분기가 섞이면 거절하는지 확인한다."""
    # when·then: 범위 밖 분기를 정규화하면 분기 선택 오류가 난다
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        normalize_quarters(bad)


def test_quarters_span_runs_from_the_first_quarter_start_to_the_last_quarter_end() -> None:
    """분기 집합의 범위가 첫 분기 시작부터 마지막 분기 끝까지인지 확인한다."""
    # when: 1·3분기 범위를 구한다
    result = quarters_span(2026, frozenset({1, 3}))
    # then: 1월 1일~9월 30일이다
    assert result == (date(2026, 1, 1), date(2026, 9, 30))


def test_quarters_span_of_one_quarter_is_that_quarter() -> None:
    """분기 하나의 범위가 그 분기인지 확인한다."""
    # when: 4분기 범위를 구한다
    result = quarters_span(2026, frozenset({4}))
    # then: 10월 1일~12월 31일이다
    assert result == (date(2026, 10, 1), date(2026, 12, 31))


def test_quarters_span_without_quarters_is_the_whole_year() -> None:
    """분기 집합이 없으면 한 해 전체인지 확인한다."""
    # when: 분기 없이 범위를 구한다
    result = quarters_span(2026, None)
    # then: 한 해 전체다
    assert result == (date(2026, 1, 1), date(2026, 12, 31))
