"""날짜 기간 조건의 허용 범위: 1900-01-01 ~ 2999-12-31, 밖은 InvalidValueError(422 invalid-value).

Deal 목록의 updated_from/to(DealQuery)와 Action 검색의 acted_from/to(DealActionQuery)에 적용한다.
극단 날짜가 window 계산에서 OverflowError·ValueError(500)가 되지 않게 하는 경계다.
시간대는 KST로 고정한다(0001-01-01의 로컬 00:00 → UTC 변환이 0년이 되는 경로를 만든다).
"""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_action_repository import DealActionQuery
from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from tests.factories import make_deal_code

if TYPE_CHECKING:
    from collections.abc import Callable

OUT_OF_RANGE = [date(1899, 12, 31), date(3000, 1, 1), date(1, 1, 1), date(9999, 12, 31)]
EDGES = [date(1900, 1, 1), date(2999, 12, 31)]


def _deal_query(**criteria: Any) -> DealQuery:  # noqa: ANN401
    return DealQuery(**criteria)


def _action_query(**criteria: Any) -> DealActionQuery:  # noqa: ANN401
    return DealActionQuery(deal_code=make_deal_code(), **criteria)


@pytest.mark.parametrize("field", ["updated_from", "updated_to"])
@pytest.mark.parametrize("day", OUT_OF_RANGE)
def test_deal_query_updated_date_outside_1900_2999_is_rejected(
    field: str, day: date, local_tz: Callable[[str], None]
) -> None:
    local_tz("Asia/Seoul")

    with pytest.raises(InvalidValueError):
        _deal_query(**{field: day})


@pytest.mark.parametrize("field", ["acted_from", "acted_to"])
@pytest.mark.parametrize("day", OUT_OF_RANGE)
def test_action_query_acted_date_outside_1900_2999_is_rejected(
    field: str, day: date, local_tz: Callable[[str], None]
) -> None:
    local_tz("Asia/Seoul")

    with pytest.raises(InvalidValueError):
        _action_query(**{field: day})


@pytest.mark.parametrize("day", EDGES)
def test_deal_query_updated_window_works_at_both_range_edges(
    day: date, local_tz: Callable[[str], None]
) -> None:
    local_tz("Asia/Seoul")

    start, end = _deal_query(updated_from=day, updated_to=day).updated_window()

    assert start is not None
    assert end is not None
    assert start < end


@pytest.mark.parametrize("day", EDGES)
def test_action_query_acted_window_works_at_both_range_edges(
    day: date, local_tz: Callable[[str], None]
) -> None:
    local_tz("Asia/Seoul")

    start, end = _action_query(acted_from=day, acted_to=day).acted_window()

    assert start is not None
    assert end is not None
    assert start < end


def test_deal_query_accepts_the_whole_allowed_span_in_one_range() -> None:
    query = _deal_query(updated_from=date(1900, 1, 1), updated_to=date(2999, 12, 31))

    assert query.updated_window() != (None, None)


def test_action_query_accepts_the_whole_allowed_span_in_one_range() -> None:
    query = _action_query(acted_from=date(1900, 1, 1), acted_to=date(2999, 12, 31))

    assert query.acted_window() != (None, None)
