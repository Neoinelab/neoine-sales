"""DealQuery의 연/분기 조건: 검증과 `revenue_window()`.

revenue_window는 (시작, 끝) 양끝 포함이고 None은 한쪽이 열려 있다는 뜻이다. 연/분기만 반영한다.
검증 오류는 만들 때 또는 `revenue_window()`에서 올라온다.
"""

from datetime import date

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with


def _window(**criteria: object) -> tuple[date | None, date | None]:
    return DealQuery(**criteria).revenue_window()  # type: ignore[arg-type]


def test_no_year_and_no_period_means_an_open_window() -> None:
    """연도와 기간이 없으면 매출 기간은 양쪽이 열려 있다."""
    # when: 조건 없이 매출 기간을 구한다
    window = _window()
    # then: 양쪽이 열려 있다
    assert window == (None, None)


def test_a_year_alone_is_january_first_to_december_31() -> None:
    """연도만 주면 그 해 1월 1일부터 12월 31일까지다."""
    # when: 연도만 주고 매출 기간을 구한다
    window = _window(year=2026)
    # then: 1월 1일~12월 31일이다
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
def test_a_year_and_quarter_is_that_quarter(quarter: int, start: date, end: date) -> None:
    """연도와 분기를 주면 그 분기의 시작일과 말일이 매출 기간이다."""
    # when: 연도와 분기로 매출 기간을 구한다
    window = _window(year=2026, quarters=frozenset({quarter}))
    # then: 그 분기의 시작일~말일이다
    assert window == (start, end)


def test_the_updated_period_does_not_change_the_revenue_window() -> None:
    """최종 업데이트 기간은 매출 기간에 영향을 주지 않는다."""
    # when: 연도·분기와 최종 업데이트 기간을 함께 주고 매출 기간을 구한다
    window = _window(
        year=2026,
        quarters=frozenset({2}),
        updated_from=date(2026, 5, 10),
        updated_to=date(2026, 5, 20),
    )
    # then: 분기 기간만 반영된다
    assert window == (date(2026, 4, 1), date(2026, 6, 30))


def test_the_updated_period_alone_leaves_the_revenue_window_open() -> None:
    """최종 업데이트 기간만 주면 매출 기간은 열려 있다."""
    # when: 최종 업데이트 기간만 주고 매출 기간을 구한다
    window = _window(updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30))
    # then: 양쪽이 열려 있다
    assert window == (None, None)


def test_a_quarter_without_a_year_is_no_longer_rejected_at_creation() -> None:
    """연도 없는 분기도 조건을 만들 때는 거부하지 않는다."""
    # when: 연도 없이 분기만 가진 조회 조건을 만든다
    query = DealQuery(quarters=frozenset({2}))
    # then: 분기가 그대로 보존된다
    assert query.quarters == frozenset({2})


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_a_quarter_outside_one_to_four_is_rejected_even_without_a_year(quarter: int) -> None:
    """연도가 없어도 1~4 밖의 분기는 거부한다."""
    # when·then: 범위 밖 분기로 조건을 만들면 값 오류다
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        DealQuery(quarters=frozenset({quarter}))


def test_revenue_window_of_an_unresolved_quarter_is_a_programming_error() -> None:
    """연도가 채워지지 않은 분기로 매출 기간을 구하면 사용자 오류가 아닌 프로그래밍 오류다."""
    # given: 연도 없는 분기 조건(올해 채우기는 ListDeals 몫)
    query = DealQuery(quarters=frozenset({2}))
    # when·then: 매출 기간을 구하면 ValueError가 난다
    with pytest.raises(ValueError) as raised:  # noqa: PT011 - 호출 순서 오류
        query.revenue_window()
    # then: 사용자 입력 오류(422)는 아니다
    assert not isinstance(raised.value, InvalidValueError)


def test_with_year_for_fills_this_year_only_when_quarter_has_no_year() -> None:
    """분기만 있고 연도가 없으면 기준일의 올해로 연도를 채운다."""
    # given: 연도 없이 분기와 키워드를 가진 조건과 기준일
    today = date(2026, 10, 19)
    # when: 기준일로 연도를 채운다
    filled = DealQuery(quarters=frozenset({2}), keyword="erp").with_year_for(today)
    # then: 연도만 채워지고 나머지는 유지되며 매출 기간이 계산된다
    assert (filled.year, filled.quarters, filled.keyword) == (2026, frozenset({2}), "erp")
    assert filled.revenue_window() == (date(2026, 4, 1), date(2026, 6, 30))


def test_with_year_for_keeps_an_explicit_year() -> None:
    """연도를 직접 지정했으면 기준일로 덮어쓰지 않는다."""
    # given: 2025년과 분기를 지정한 조건
    query = DealQuery(year=2025, quarters=frozenset({2}))
    # when: 2026년 기준일로 연도를 채운다
    filled = query.with_year_for(date(2026, 10, 19))
    # then: 연도는 2025년 그대로다
    assert filled.year == 2025


def test_with_year_for_leaves_a_query_without_quarter_alone() -> None:
    """분기가 없는 조건은 연도를 채우지 않는다."""
    # given: 분기 없는 조건
    query = DealQuery(keyword="erp")
    # when: 기준일로 연도를 채운다
    filled = query.with_year_for(date(2026, 10, 19))
    # then: 연도는 비어 있고, 연도만 지정한 조건도 그대로다
    assert filled.year is None
    assert DealQuery(year=2025).with_year_for(date(2026, 10, 19)).year == 2025


def test_with_year_for_does_not_change_the_original_query() -> None:
    """연도 채우기는 원래 조건 객체를 바꾸지 않는다."""
    # given: 연도 없는 분기 조건
    query = DealQuery(quarters=frozenset({3}))
    # when: 기준일로 연도를 채운다
    query.with_year_for(date(2026, 10, 19))
    # then: 원래 조건의 연도는 비어 있다
    assert query.year is None


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_a_quarter_outside_one_to_four_is_rejected(quarter: int) -> None:
    """1~4 밖의 분기는 거부한다."""
    # when·then: 범위 밖 분기로 매출 기간을 구하면 값 오류다
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        _window(year=2026, quarters=frozenset({quarter}))


@pytest.mark.parametrize("year", [1899, 10000, 0, -1])
def test_a_year_outside_1900_to_9999_is_rejected(year: int) -> None:
    """1900~9999 밖의 연도는 거부한다."""
    # when·then: 범위 밖 연도로 매출 기간을 구하면 값 오류다
    with pytest.raises(InvalidValueError):
        _window(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_the_year_boundaries_are_accepted(year: int) -> None:
    """연도 경계값 1900과 9999는 허용한다."""
    # when: 경계 연도와 4분기로 매출 기간을 구한다
    window = _window(year=year, quarters=frozenset({4}))
    # then: 그 해 12월 31일이 끝이다
    assert window[1] == date(year, 12, 31)
