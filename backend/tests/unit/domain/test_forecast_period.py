"""ForecastPeriod: 연 / 연+분기 / 연+월 기간, 양끝 포함, 분기와 월은 배타."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.forecast.errors import QUARTER_MONTH_EXCLUSIVE
from app.domain.forecast.period import ForecastPeriod
from tests.support.expect import raises_with


def test_year_only_period_covers_whole_year() -> None:
    """연도만 있는 기간은 그 해 1월 1일부터 12월 31일까지다"""
    # given: 2026년 기간
    period = ForecastPeriod(year=2026)

    # when: 날짜 범위를 구한다
    window = period.date_range()
    # then: 1/1~12/31이다
    assert window == (date(2026, 1, 1), date(2026, 12, 31))


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
    """분기 기간은 분기 첫날부터 마지막 날까지다"""
    # when: 분기 기간의 날짜 범위를 구한다
    window = ForecastPeriod(year=2026, quarters=frozenset({quarter})).date_range()
    # then: 그 분기의 첫날~마지막 날이다
    assert window == (start, end)


@pytest.mark.parametrize(
    ("year", "month", "last_day"),
    [(2026, 1, 31), (2026, 2, 28), (2028, 2, 29), (2026, 4, 30), (2026, 12, 31)],
)
def test_month_period_ends_on_month_last_day(year: int, month: int, last_day: int) -> None:
    """월 기간은 그 달 1일부터 말일까지이고 윤년 2월은 29일이다"""
    # given: 연·월 기간
    period = ForecastPeriod(year=year, month=month)

    # when: 날짜 범위를 구한다
    window = period.date_range()
    # then: 1일~말일이다
    assert window == (date(year, month, 1), date(year, month, last_day))


def test_december_31_belongs_to_q4_and_jan_1_to_next_year() -> None:
    """12월 31일은 그 해 Q4에, 1월 1일은 다음 해 Q1·1월에 속한다"""
    # given: 2026 Q4, 2027 Q1, 2027년 1월 기간
    q4 = ForecastPeriod(year=2026, quarters=frozenset({4}))
    next_q1 = ForecastPeriod(year=2027, quarters=frozenset({1}))
    next_january = ForecastPeriod(year=2027, month=1)

    # when: 경계 날짜를 판정한다
    q4_last = q4.contains(date(2026, 12, 31))
    q4_next = q4.contains(date(2027, 1, 1))
    q1_first = next_q1.contains(date(2027, 1, 1))
    jan_first = next_january.contains(date(2027, 1, 1))
    jan_prev = next_january.contains(date(2026, 12, 31))

    # then: 12-31은 Q4에만, 1-1은 다음 해 Q1·1월에만 든다
    assert q4_last
    assert not q4_next
    assert q1_first
    assert jan_first
    assert not jan_prev


def test_contains_is_inclusive_at_both_ends_and_false_outside() -> None:
    """기간 양끝은 포함하고 바깥은 포함하지 않는다"""
    # given: 2026 Q4 기간
    q4 = ForecastPeriod(year=2026, quarters=frozenset({4}))

    # when: 양끝과 바깥 날짜를 판정한다
    first = q4.contains(date(2026, 10, 1))
    last = q4.contains(date(2026, 12, 31))
    before = q4.contains(date(2026, 9, 30))

    # then: 10-01·12-31은 들고 9-30은 들지 않는다
    assert first
    assert last
    assert not before


def test_quarter_and_month_together_raise_invalid_value() -> None:
    """Quarter와 월을 함께 주면 InvalidValueError다"""
    # when·then: 분기 1과 월 1로 만들면 안내 문구의 InvalidValueError다
    with raises_with(InvalidValueError, QUARTER_MONTH_EXCLUSIVE):
        ForecastPeriod(year=2026, quarters=frozenset({1}), month=1)


def test_the_exclusive_message_is_the_documented_text() -> None:
    """Quarter·월 동시 선택 오류 문구는 문서와 같다"""
    # when: 오류 문구 상수를 읽는다
    message = QUARTER_MONTH_EXCLUSIVE
    # then: 문서의 문구와 같다
    assert message == "Quarter와 월은 함께 선택할 수 없습니다."


@pytest.mark.parametrize("month", [0, 13, -1])
def test_month_out_of_range_raises_invalid_value(month: int) -> None:
    """월이 1~12 밖이면 InvalidValueError다"""
    # when·then: 범위 밖 월로 만들면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=2026, month=month)


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_out_of_range_raises_invalid_value(quarter: int) -> None:
    """분기가 1~4 밖이면 InvalidValueError다"""
    # when·then: 범위 밖 분기로 만들면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=2026, quarters=frozenset({quarter}))


@pytest.mark.parametrize("year", [1899, 10000])
def test_year_out_of_range_raises_invalid_value(year: int) -> None:
    """연도가 1900~9999 밖이면 InvalidValueError다"""
    # when·then: 범위 밖 연도로 만들면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        ForecastPeriod(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_year_bounds_are_accepted(year: int) -> None:
    """연도 1900과 9999는 허용한다"""
    # when: 경계 연도의 날짜 범위를 구한다
    start = ForecastPeriod(year=year).date_range()[0]
    # then: 시작일이 그 해 1월 1일이다
    assert start == date(year, 1, 1)


# ---- 분기 집합(Quarter 다중 선택) ----


def test_a_set_of_separated_quarters_spans_first_start_to_last_end() -> None:
    """떨어진 분기 집합의 범위는 첫 분기 시작부터 마지막 분기 끝까지다"""
    # given: Q1·Q3를 고른 기간
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    # when: 날짜 범위를 구한다
    window = period.date_range()
    # then: 1/1~9/30이다
    assert window == (date(2026, 1, 1), date(2026, 9, 30))


def test_contains_follows_the_chosen_quarters_not_the_gap_between_them() -> None:
    """포함 판정은 고른 분기를 따르고 사이의 분기는 뺀다"""
    # given: Q1·Q3를 고른 기간
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    # when: 분기 안팎의 날짜를 판정한다
    q1_end = period.contains(date(2026, 3, 31))
    q3_start = period.contains(date(2026, 7, 1))
    q2_start = period.contains(date(2026, 4, 1))
    q2_end = period.contains(date(2026, 6, 30))
    q4_start = period.contains(date(2026, 10, 1))
    prev_year = period.contains(date(2025, 12, 31))

    # then: 고른 분기의 날짜는 들고 Q2·Q4·전년 날짜는 들지 않는다
    assert q1_end
    assert q3_start
    assert not q2_start
    assert not q2_end
    assert not q4_start
    assert not prev_year


def test_single_quarter_and_sorted_quarters_describe_the_selection() -> None:
    """단일 분기·정렬된 분기 목록이 선택을 설명한다"""
    # given: Q1·Q3, Q2 하나, 분기 없는 기간
    several = ForecastPeriod(year=2026, quarters=frozenset({3, 1}))
    one = ForecastPeriod(year=2026, quarters=frozenset({2}))
    none = ForecastPeriod(year=2026)

    # when: single_quarter와 sorted_quarters를 읽는다
    several_view = (several.single_quarter, several.sorted_quarters())
    one_view = (one.single_quarter, one.sorted_quarters())
    none_view = (none.single_quarter, none.sorted_quarters())

    # then: 선택에 맞다
    assert several_view == (None, (1, 3))
    assert one_view == (2, (2,))
    assert none_view == (None, ())


def test_all_four_quarters_are_normalized_to_no_quarter_condition() -> None:
    """네 분기를 모두 고르면 분기 조건 없음으로 정규화된다"""
    # when: Q1~Q4를 모두 골라 만든다
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 2, 3, 4}))

    # then: 분기 조건이 없고 연도만 있는 기간과 같다
    assert period.quarters is None
    assert period == ForecastPeriod(year=2026)
    assert period.sorted_quarters() == ()


def test_an_empty_quarter_set_is_normalized_to_no_quarter_condition() -> None:
    """빈 분기 집합은 분기 조건 없음으로 정규화된다"""
    # when: 빈 분기 집합으로 만든다
    quarters = ForecastPeriod(year=2026, quarters=frozenset()).quarters
    # then: 분기 조건이 없다
    assert quarters is None


def test_chosen_quarters_and_month_together_raise_invalid_value() -> None:
    """고른 분기와 월을 함께 주면 InvalidValueError다"""
    # when·then: 분기 1과 월 2로 만들면 InvalidValueError다
    with raises_with(InvalidValueError, QUARTER_MONTH_EXCLUSIVE):
        ForecastPeriod(year=2026, quarters=frozenset({1}), month=2)


def test_all_four_quarters_with_a_month_are_accepted_as_a_month_only_period() -> None:
    """네 분기와 월을 함께 주면 월 기간으로 받아들인다"""
    # when: Q1~Q4와 5월을 함께 준다
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 2, 3, 4}), month=5)

    # then: 5월 1일~31일 기간이다
    assert period.date_range() == (date(2026, 5, 1), date(2026, 5, 31))


@pytest.mark.parametrize(("month", "expected"), [(1, True), (3, True), (5, False), (8, True)])
def test_contains_month_follows_the_chosen_quarters(month: int, expected: bool) -> None:
    """월 포함 판정은 고른 분기의 달을 따른다"""
    # given: Q1·Q3를 고른 기간
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    # when: 그 달이 기간에 드는지 본다
    contained = period.contains_month(2026, month)
    # then: 분기에 드는 달만 참이다
    assert contained is expected


def test_contains_month_rejects_another_year() -> None:
    """다른 해의 달은 포함하지 않는다"""
    # given: 2026 Q1·Q3 기간
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    # when: 다른 해의 달을 판정한다
    in_2025 = period.contains_month(2025, 2)
    in_2027 = period.contains_month(2027, 2)

    # then: 2025년·2027년의 달은 들지 않는다
    assert not in_2025
    assert not in_2027


def test_contains_month_of_a_year_only_period_accepts_every_month_of_the_year() -> None:
    """연도만 있는 기간은 그 해 모든 달을 포함한다"""
    # given: 2026년 기간
    period = ForecastPeriod(year=2026)

    # when: 2026년 모든 달과 2027년 1월을 판정한다
    every_month = all(period.contains_month(2026, m) for m in range(1, 13))
    next_year = period.contains_month(2027, 1)

    # then: 2026년 1~12월은 들고 2027년 1월은 들지 않는다
    assert every_month
    assert not next_year


def test_contains_month_of_a_month_period_accepts_only_that_month() -> None:
    """월 기간은 그 달만 포함한다"""
    # given: 2026년 4월 기간
    period = ForecastPeriod(year=2026, month=4)

    # when: 4월과 5월을 판정한다
    april = period.contains_month(2026, 4)
    may = period.contains_month(2026, 5)

    # then: 4월은 들고 5월은 들지 않는다
    assert april
    assert not may
