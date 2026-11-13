"""DealActionQuery: Deal 필수, 날짜 범위(양끝 포함, 로컬 업무 날짜), 정렬 10종, 검색어."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.application.ports.deal_action_repository import DealActionQuery, DealActionSort
from app.domain.common.errors import InvalidValueError
from tests.factories import make_deal_code
from tests.support.expect import raises_with

CODE = make_deal_code()


def _query(**criteria: Any) -> DealActionQuery:  # noqa: ANN401
    return DealActionQuery(deal_code=CODE, **criteria)


def test_the_query_requires_a_deal_because_the_global_search_is_gone() -> None:
    """Deal 없이는 Action 조회 조건을 만들 수 없다(전역 검색 없음).

    테스트 코드: NA-022
    """
    # when·then: Deal code 없이 조건을 만들면 TypeError다
    with pytest.raises(TypeError):
        DealActionQuery()  # type: ignore[call-arg]


@pytest.mark.parametrize("removed", [{"offset": 0}, {"limit": 10}, {"actor": "kim"}])
def test_the_query_has_no_paging_and_no_free_text_actor(removed: dict[str, Any]) -> None:
    """조회 조건에는 offset·limit·자유 텍스트 담당자가 없다.

    테스트 코드: NA-019, NA-036
    """
    # when·then: 폐지된 조건을 주면 TypeError다
    with pytest.raises(TypeError):
        DealActionQuery(deal_code=CODE, **removed)


def test_sort_values_are_the_ten_api_names_and_the_default_is_latest_first() -> None:
    """정렬 값은 정해진 10개이고 기본은 수행일시 최신순이다.

    테스트 코드: NA-043, NA-019
    """
    # when: 정렬 값과 기본 조건의 정렬을 읽는다
    values = [s.value for s in DealActionSort]
    default = _query().sort
    # then: 10개 값이고 기본은 acted_at_desc다
    assert values == [
        "acted_at_desc",
        "acted_at_asc",
        "due_date_asc",
        "due_date_desc",
        "actor_asc",
        "actor_desc",
        "action_type_asc",
        "action_type_desc",
        "next_action_status_asc",
        "next_action_status_desc",
    ]
    assert default is DealActionSort.ACTED_AT_DESC


def test_action_query_rejects_reversed_ranges_with_messages() -> None:
    """시작이 끝보다 늦은 범위는 InvalidValueError이고 문구가 범위 종류를 알려 준다.

    테스트 코드: NA-031
    """
    # when·then: 수행일 범위가 거꾸로면 수행일 문구다
    with raises_with(InvalidValueError, "수행일 범위의 시작은 끝보다 늦을 수 없습니다."):
        _query(acted_from=date(2026, 10, 17), acted_to=date(2026, 10, 16))
    # when·then: Due Date 범위가 거꾸로면 Due Date 문구다
    with raises_with(InvalidValueError, "Due Date 범위의 시작은 끝보다 늦을 수 없습니다."):
        _query(due_from=date(2026, 3, 2), due_to=date(2026, 3, 1))


def test_equal_range_bounds_are_allowed() -> None:
    """시작과 끝이 같은 날인 범위는 허용된다.

    테스트 코드: NA-031
    """
    # when: 수행일·Due Date 범위의 시작과 끝을 같은 날로 만든다
    query = _query(
        acted_from=date(2026, 10, 16),
        acted_to=date(2026, 10, 16),
        due_from=date(2026, 3, 1),
        due_to=date(2026, 3, 1),
    )

    # then: 오류 없이 만들어진다
    assert query.due_from == query.due_to
    assert query.acted_from == query.acted_to


@pytest.mark.parametrize("name", ["acted_from", "acted_to", "due_from", "due_to"])
def test_a_datetime_is_not_a_calendar_date(name: str) -> None:
    """날짜 조건에 시각이 있는 값을 주면 거절한다.

    테스트 코드: NA-036
    """
    # when·then: 시각이 있는 값을 날짜 조건에 주면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        _query(**{name: datetime(2026, 10, 16, 9, 0, tzinfo=UTC)})


def test_keyword_is_trimmed_and_limited_to_one_hundred() -> None:
    """검색어는 앞뒤 공백을 지우고 공백뿐이면 조건이 없으며 100자까지 허용한다.

    테스트 코드: NA-027, NA-028
    """
    # when: 공백이 붙은 검색어, 공백뿐인 검색어, 100자 검색어로 조건을 만든다
    padded = _query(keyword="  견적  ")
    blank = _query(keyword="   ")
    longest = _query(keyword="가" * 100)
    # then: 공백은 지워지고 공백뿐이면 없으며 100자는 그대로다
    assert padded.keyword == "견적"
    assert blank.keyword is None
    assert longest.keyword == "가" * 100


def test_keyword_longer_than_one_hundred_is_rejected() -> None:
    """검색어가 100자를 넘으면 InvalidValueError다.

    테스트 코드: NA-028
    """
    # when·then: 101자 검색어로 조건을 만들면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        _query(keyword="가" * 101)


def test_keyword_with_nul_is_rejected_with_the_nul_message() -> None:
    """검색어에 NUL 문자가 있으면 InvalidValueError이고 문구가 NUL을 알려 준다.

    테스트 코드: NA-028
    """
    # when·then: NUL이 든 검색어로 조건을 만들면 NUL 문구의 InvalidValueError다
    with raises_with(InvalidValueError, "검색어에는 NUL 문자를 쓸 수 없습니다"):
        _query(keyword="a\x00b")
