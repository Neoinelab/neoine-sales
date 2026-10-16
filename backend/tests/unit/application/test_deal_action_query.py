"""DealActionQuery(AC-15·16): Deal 필수, 날짜 범위(양끝 포함, 로컬 업무 날짜), 정렬 3종, 검색어."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_action_repository import DealActionQuery, DealActionSort
from app.domain.common.errors import InvalidValueError
from tests.factories import make_deal_code
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from collections.abc import Callable

CODE = make_deal_code()


def _query(**criteria: Any) -> DealActionQuery:  # noqa: ANN401
    return DealActionQuery(deal_code=CODE, **criteria)


def test_the_query_requires_a_deal_because_the_global_search_is_gone() -> None:
    with pytest.raises(TypeError):
        DealActionQuery()  # type: ignore[call-arg]


@pytest.mark.parametrize("removed", [{"offset": 0}, {"limit": 10}, {"actor": "kim"}])
def test_the_query_has_no_paging_and_no_free_text_actor(removed: dict[str, Any]) -> None:
    with pytest.raises(TypeError):
        DealActionQuery(deal_code=CODE, **removed)


def test_sort_values_are_the_three_api_names_and_the_default_is_latest_first() -> None:
    assert [s.value for s in DealActionSort] == ["acted_at_desc", "acted_at_asc", "due_date_asc"]
    assert _query().sort is DealActionSort.ACTED_AT_DESC


def test_acted_window_covers_whole_local_days(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")

    window = _query(acted_from=date(2026, 10, 16), acted_to=date(2026, 10, 16)).acted_window()

    # [10-16 00:00 로컬, 10-17 00:00 로컬)
    assert window == (
        datetime(2026, 10, 15, 15, 0, tzinfo=UTC),
        datetime(2026, 10, 16, 15, 0, tzinfo=UTC),
    )


def test_acted_window_with_a_longer_range_ends_after_the_last_day(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("UTC")

    window = _query(acted_from=date(2026, 10, 1), acted_to=date(2026, 10, 31)).acted_window()

    assert window == (
        datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
    )


def test_acted_window_leaves_an_open_side_open() -> None:
    assert _query().acted_window() == (None, None)
    start, end = _query(acted_from=date(2026, 10, 16)).acted_window()
    assert start is not None
    assert end is None
    start, end = _query(acted_to=date(2026, 10, 16)).acted_window()
    assert start is None
    assert end is not None


def test_action_query_rejects_reversed_ranges_with_messages() -> None:
    with raises_with(InvalidValueError, "수행일 범위의 시작은 끝보다 늦을 수 없습니다."):
        _query(acted_from=date(2026, 10, 17), acted_to=date(2026, 10, 16))
    with raises_with(InvalidValueError, "Due Date 범위의 시작은 끝보다 늦을 수 없습니다."):
        _query(due_from=date(2026, 3, 2), due_to=date(2026, 3, 1))


def test_equal_range_bounds_are_allowed() -> None:
    query = _query(
        acted_from=date(2026, 10, 16),
        acted_to=date(2026, 10, 16),
        due_from=date(2026, 3, 1),
        due_to=date(2026, 3, 1),
    )

    assert query.due_from == query.due_to


@pytest.mark.parametrize("name", ["acted_from", "acted_to", "due_from", "due_to"])
def test_a_datetime_is_not_a_calendar_date(name: str) -> None:
    with pytest.raises(InvalidValueError):
        _query(**{name: datetime(2026, 10, 16, 9, 0, tzinfo=UTC)})


def test_keyword_is_trimmed_limited_to_one_hundred_and_rejects_nul() -> None:
    assert _query(keyword="  견적  ").keyword == "견적"
    assert _query(keyword="   ").keyword is None
    assert _query(keyword="가" * 100).keyword == "가" * 100
    with pytest.raises(InvalidValueError):
        _query(keyword="가" * 101)
    with pytest.raises(InvalidValueError):
        _query(keyword="a\x00b")
