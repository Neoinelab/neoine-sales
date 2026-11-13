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
from tests.support.expect import raises_with

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
    """1900~2999년 밖의 Deal 최종 업데이트 날짜 조건은 InvalidValueError로 거절된다."""
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")

    # when·then: 범위 밖 날짜를 updated_from 또는 updated_to로 주면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        _deal_query(**{field: day})


@pytest.mark.parametrize("field", ["acted_from", "acted_to"])
@pytest.mark.parametrize("day", OUT_OF_RANGE)
def test_action_query_acted_date_outside_1900_2999_is_rejected(
    field: str, day: date, local_tz: Callable[[str], None]
) -> None:
    """1900~2999년 밖의 수행일은 InvalidValueError이고 문구가 허용 범위를 알려 준다.

    테스트 코드: NA-032
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when·then: 범위 밖 날짜를 acted_from 또는 acted_to로 주면 422 문구다
    with raises_with(InvalidValueError, f"{field}은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"):
        _action_query(**{field: day})


@pytest.mark.parametrize("day", EDGES)
def test_deal_query_updated_dates_work_at_both_range_edges(
    day: date, local_tz: Callable[[str], None]
) -> None:
    """허용 범위의 양 끝 날짜(1900-01-01, 2999-12-31)는 Deal 조회 구간으로 바뀐다."""
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")

    # when: 양 끝 날짜로 최종 업데이트 구간을 구한다
    query = _deal_query(updated_from=day, updated_to=day)

    # then: 거부되지 않고 그 날짜가 그대로 조건이 된다
    assert (query.updated_from, query.updated_to) == (day, day)


@pytest.mark.parametrize("day", EDGES)
def test_action_query_acted_dates_work_at_both_range_edges(
    day: date, local_tz: Callable[[str], None]
) -> None:
    """허용 범위의 양 끝 날짜(1900-01-01, 2999-12-31)는 조회 구간으로 바뀐다.

    테스트 코드: NA-032
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: 양 끝 날짜로 수행 구간을 구한다
    query = _action_query(acted_from=day, acted_to=day)
    # then: 거부되지 않고 그 날짜가 그대로 조건이 된다
    assert (query.acted_from, query.acted_to) == (day, day)


def test_deal_query_accepts_the_whole_allowed_span_in_one_range() -> None:
    """허용 범위 전체를 한 범위로 Deal 조회 조건에 줄 수 있다."""
    # when: 1900-01-01부터 2999-12-31까지 범위로 조건을 만든다
    query = _deal_query(updated_from=date(1900, 1, 1), updated_to=date(2999, 12, 31))

    # then: 거부되지 않고 조건이 된다
    assert (query.updated_from, query.updated_to) == (date(1900, 1, 1), date(2999, 12, 31))


def test_action_query_accepts_the_whole_allowed_span_in_one_range() -> None:
    """허용 범위 전체를 한 범위로 줄 수 있다.

    테스트 코드: NA-032
    """
    # when: 1900-01-01부터 2999-12-31까지 범위로 조건을 만든다
    query = _action_query(acted_from=date(1900, 1, 1), acted_to=date(2999, 12, 31))
    # then: 거부되지 않고 조건이 된다
    assert (query.acted_from, query.acted_to) == (date(1900, 1, 1), date(2999, 12, 31))
