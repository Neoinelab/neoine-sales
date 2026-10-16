"""DealQuery의 연/분기·BANT 조건(AC-22b·22c): 검증과 `revenue_window()`(기간과의 교집합).

window는 (시작, 끝) 양끝 포함이고 None은 한쪽이 열려 있다는 뜻이다. 시작이 끝보다 늦으면 빈
창이며 오류가 아니다(0건). 검증 오류는 만들 때 또는 `revenue_window()`에서 올라온다.
"""

from datetime import date

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.errors import InvalidValueError
from tests.factories import new_contact_id
from tests.support.expect import raises_with


def _window(**criteria: object) -> tuple[date | None, date | None]:
    return DealQuery(**criteria).revenue_window()  # type: ignore[arg-type]


def test_no_year_and_no_period_means_an_open_window() -> None:
    assert _window() == (None, None)


def test_a_period_without_a_year_is_the_window_itself() -> None:
    assert _window(revenue_from=date(2026, 6, 1)) == (date(2026, 6, 1), None)
    assert _window(revenue_to=date(2026, 6, 30)) == (None, date(2026, 6, 30))


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
    assert _window(year=2026, quarter=quarter) == (start, end)


def test_a_period_inside_the_quarter_narrows_it() -> None:
    window = _window(
        year=2026, quarter=2, revenue_from=date(2026, 5, 10), revenue_to=date(2026, 5, 20)
    )

    assert window == (date(2026, 5, 10), date(2026, 5, 20))


def test_a_period_wider_than_the_quarter_is_clipped_to_it() -> None:
    window = _window(
        year=2026, quarter=2, revenue_from=date(2026, 1, 1), revenue_to=date(2026, 12, 31)
    )

    assert window == (date(2026, 4, 1), date(2026, 6, 30))


def test_a_period_overlapping_one_end_of_the_quarter_keeps_the_overlap() -> None:
    assert _window(year=2026, quarter=2, revenue_from=date(2026, 5, 15)) == (
        date(2026, 5, 15),
        date(2026, 6, 30),
    )
    assert _window(year=2026, quarter=2, revenue_to=date(2026, 5, 31)) == (
        date(2026, 4, 1),
        date(2026, 5, 31),
    )


def test_a_period_outside_the_year_gives_an_empty_window_not_an_error() -> None:
    start, end = _window(year=2026, revenue_from=date(2027, 1, 1))

    assert start is not None
    assert end is not None
    assert start > end


def test_a_quarter_without_a_year_is_rejected() -> None:
    with raises_with(InvalidValueError, "분기는 연도와 함께 선택하세요."):
        _window(quarter=2)


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_a_quarter_outside_one_to_four_is_rejected(quarter: int) -> None:
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        _window(year=2026, quarter=quarter)


@pytest.mark.parametrize("year", [1899, 10000, 0, -1])
def test_a_year_outside_1900_to_9999_is_rejected(year: int) -> None:
    with pytest.raises(InvalidValueError):
        _window(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_the_year_boundaries_are_accepted(year: int) -> None:
    assert _window(year=year, quarter=4)[1] == date(year, 12, 31)


def test_bant_labels_are_kept_per_category() -> None:
    budget, need = BantLabelId(new_contact_id()), BantLabelId(new_contact_id())

    query = DealQuery(bant_label_ids={BantCategory.BUDGET: budget, BantCategory.NEED: need})

    assert dict(query.bant_label_ids) == {BantCategory.BUDGET: budget, BantCategory.NEED: need}
