"""DealQuery의 연/분기 조건: 검증과 `revenue_window()`, 최종 업데이트 `updated_window()`.

revenue_window는 (시작, 끝) 양끝 포함이고 None은 한쪽이 열려 있다는 뜻이다. 연/분기만 반영한다.
updated_window는 last_updated_at의 반개구간 [시작, 끝)이다. 검증 오류는 만들 때 또는
`revenue_window()`에서 올라온다.
"""

from datetime import date, timedelta

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.business_date import start_of_business_day
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with


def _window(**criteria: object) -> tuple[date | None, date | None]:
    return DealQuery(**criteria).revenue_window()  # type: ignore[arg-type]


def test_no_year_and_no_period_means_an_open_window() -> None:
    assert _window() == (None, None)


def test_a_year_alone_is_january_first_to_december_31() -> None:
    assert _window(year=2026) == (date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.parametrize(
    ("quarter", "start", "end"),
    [
        (1, date(2026, 1, 1), date(2026, 3, 31)),
        (2, date(2026, 4, 1), date(2026, 6, 30)),
        (3, date(2026, 7, 1), date(2026, 9, 30)),
        (4, date(2026, 10, 1), date(2026, 12, 31)),
    ],
)
def test_a_year_and_quarter_is_that_quarter(quarter: int, start: date, end: date) -> None:
    assert _window(year=2026, quarters=frozenset({quarter})) == (start, end)


def test_the_updated_period_does_not_change_the_revenue_window() -> None:
    window = _window(
        year=2026,
        quarters=frozenset({2}),
        updated_from=date(2026, 5, 10),
        updated_to=date(2026, 5, 20),
    )

    assert window == (date(2026, 4, 1), date(2026, 6, 30))


def test_the_updated_period_alone_leaves_the_revenue_window_open() -> None:
    assert _window(updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30)) == (None, None)


def test_updated_window_is_half_open_by_business_day() -> None:
    query = DealQuery(updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30))

    assert query.updated_window() == (
        start_of_business_day(date(2026, 6, 1)),
        start_of_business_day(date(2026, 7, 1)),
    )


def test_updated_window_end_is_the_next_local_midnight_across_a_month_end() -> None:
    query = DealQuery(updated_to=date(2026, 12, 31))

    assert query.updated_window()[1] == start_of_business_day(
        date(2026, 12, 31) + timedelta(days=1)
    )


def test_updated_window_with_only_a_start_is_open_at_the_end() -> None:
    query = DealQuery(updated_from=date(2026, 6, 1))

    assert query.updated_window() == (start_of_business_day(date(2026, 6, 1)), None)


def test_updated_window_with_only_an_end_is_open_at_the_start() -> None:
    query = DealQuery(updated_to=date(2026, 6, 30))

    assert query.updated_window() == (None, start_of_business_day(date(2026, 7, 1)))


def test_updated_window_without_a_period_is_fully_open() -> None:
    assert DealQuery().updated_window() == (None, None)


def test_updated_window_of_a_single_day_spans_that_local_day() -> None:
    day = date(2026, 6, 15)

    start, end = DealQuery(updated_from=day, updated_to=day).updated_window()

    assert start == start_of_business_day(day)
    assert end == start_of_business_day(day + timedelta(days=1))


def test_a_quarter_without_a_year_is_no_longer_rejected_at_creation() -> None:
    assert DealQuery(quarters=frozenset({2})).quarters == frozenset({2})


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_a_quarter_outside_one_to_four_is_rejected_even_without_a_year(quarter: int) -> None:
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        DealQuery(quarters=frozenset({quarter}))


def test_revenue_window_of_an_unresolved_quarter_is_a_programming_error() -> None:
    query = DealQuery(
        quarters=frozenset({2})
    )  # 연도 없는 분기는 만들 수 있다(올해 채우기는 ListDeals 몫)

    with pytest.raises(ValueError) as raised:  # noqa: PT011 - 호출 순서 오류
        query.revenue_window()

    assert not isinstance(raised.value, InvalidValueError)  # 사용자 입력 오류(422)가 아니다


def test_with_year_for_fills_this_year_only_when_quarter_has_no_year() -> None:
    today = date(2026, 10, 19)

    filled = DealQuery(quarters=frozenset({2}), keyword="erp").with_year_for(today)

    assert (filled.year, filled.quarters, filled.keyword) == (2026, frozenset({2}), "erp")
    assert filled.revenue_window() == (date(2026, 4, 1), date(2026, 6, 30))


def test_with_year_for_keeps_an_explicit_year() -> None:
    query = DealQuery(year=2025, quarters=frozenset({2}))

    assert query.with_year_for(date(2026, 10, 19)).year == 2025


def test_with_year_for_leaves_a_query_without_quarter_alone() -> None:
    query = DealQuery(keyword="erp")

    assert query.with_year_for(date(2026, 10, 19)).year is None
    assert DealQuery(year=2025).with_year_for(date(2026, 10, 19)).year == 2025


def test_with_year_for_does_not_change_the_original_query() -> None:
    query = DealQuery(quarters=frozenset({3}))

    query.with_year_for(date(2026, 10, 19))

    assert query.year is None


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_a_quarter_outside_one_to_four_is_rejected(quarter: int) -> None:
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        _window(year=2026, quarters=frozenset({quarter}))


@pytest.mark.parametrize("year", [1899, 10000, 0, -1])
def test_a_year_outside_1900_to_9999_is_rejected(year: int) -> None:
    with pytest.raises(InvalidValueError):
        _window(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_the_year_boundaries_are_accepted(year: int) -> None:
    assert _window(year=year, quarters=frozenset({4}))[1] == date(year, 12, 31)
