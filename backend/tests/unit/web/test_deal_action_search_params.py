"""Action 검색 쿼리 파라미터: 조건 매핑, 정렬 10종, 상태 필터, 거절되는 파라미터."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.ports.deal_action_repository import (
    DealActionQuery,
    DealActionSort,
    NextActionStatusFilter,
)
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.web.schemas.deal_action import DealActionSearchParams
from tests.factories import make_deal_code
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.user_ids import uid


def test_search_params_default_to_everything_sorted_latest_first() -> None:
    """파라미터를 주지 않으면 조건 없이 수행일시 최신순이다.

    테스트 코드: NA-019
    """
    # when: 파라미터 없이 조회 조건으로 바꾼다
    query = DealActionSearchParams().to_query("20261016-A001")
    # then: 조건이 없고 정렬은 acted_at_desc다
    assert query == DealActionQuery(deal_code=make_deal_code("A001"))
    assert query.sort is DealActionSort.ACTED_AT_DESC


def test_search_params_map_every_condition() -> None:
    """유형·담당자·검색어·수행일·Due Date·정렬 파라미터가 조회 조건에 그대로 옮겨진다.

    테스트 코드: NA-023, NA-029, NA-030
    """
    # given: 모든 조건을 채운 쿼리 파라미터
    email_id = new_id()
    params = DealActionSearchParams(
        action_type_id=email_id,
        actor_user_id=uid("kim"),
        keyword=" 견적 ",
        acted_from="2026-10-01",
        acted_to="2026-10-31",
        due_from="2026-11-01",
        due_to="2026-11-30",
        sort="due_date_asc",
    )

    # when: 조회 조건으로 바꾼다
    query = params.to_query("20261016-A001")
    # then: 검색어는 trim되고 나머지는 그대로다
    assert query.deal_code == make_deal_code("A001")
    assert query.action_type_id == email_id
    assert query.actor_user_id == uid("kim")
    assert query.keyword == "견적"
    assert (query.acted_from, query.acted_to) == (date(2026, 10, 1), date(2026, 10, 31))
    assert (query.due_from, query.due_to) == (date(2026, 11, 1), date(2026, 11, 30))
    assert query.sort is DealActionSort.DUE_DATE_ASC


@pytest.mark.parametrize("value", ["open", "done", "not_done", "closed"])
def test_search_params_pass_the_next_action_status_filter(value: str) -> None:
    """상태 필터 4값은 조회 조건의 필터로 그대로 전달된다.

    테스트 코드: NA-033
    """
    # when: 상태 필터 값을 조회 조건으로 바꾼다
    query = DealActionSearchParams(next_action_status=value).to_query("20261016-A001")
    # then: 같은 필터 값이다
    assert query.next_action_status == NextActionStatusFilter(value)


def test_search_params_default_to_no_status_filter() -> None:
    """상태 필터를 주지 않으면 필터가 없다(진행사항만 Action도 나온다).

    테스트 코드: NA-033
    """
    # when·then: 파라미터 없이 바꾼 조회 조건에는 상태 필터가 없다
    assert DealActionSearchParams().to_query("20261016-A001").next_action_status is None


@pytest.mark.parametrize("value", ["notDone", "DONE", "all", "", "close"])
def test_any_other_status_filter_is_rejected(value: str) -> None:
    """허용하지 않는 상태 필터 값은 요청 형식 오류다.

    테스트 코드: NA-035
    """
    # when·then: notDone·DONE·all·빈 문자열·close는 ValidationError다
    with pytest.raises(ValidationError):
        DealActionSearchParams(next_action_status=value)


@pytest.mark.parametrize(
    "sort",
    [
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
    ],
)
def test_every_sort_value_is_accepted(sort: str) -> None:
    """정해진 10개 정렬 값은 받아들인다.

    테스트 코드: NA-043
    """
    # when·then: 각 정렬 값이 그대로 받아들여진다
    assert DealActionSearchParams(sort=sort).sort.value == sort


@pytest.mark.parametrize(
    "sort", ["created_asc", "DUE_DATE_ASC", "", "actor", "status_asc", "ACTOR_ASC"]
)
def test_any_other_sort_is_rejected(sort: str) -> None:
    """그 밖의 정렬 값(대소문자 다름 포함)은 요청 형식 오류다.

    테스트 코드: NA-043
    """
    # when·then: 정해진 값이 아니면 ValidationError다
    with pytest.raises(ValidationError):
        DealActionSearchParams(sort=sort)


@pytest.mark.parametrize("field", ["actor_user_id", "action_type_id"])
@pytest.mark.parametrize("bad", ["abc", "1.5", "0", "-1", 0, -1, 2**53, "9007199254740992"])
def test_id_query_parameters_must_be_positive_integers(field: str, bad: object) -> None:
    """유형 id·담당자 id 파라미터는 양의 정수여야 한다.

    테스트 코드: NA-036
    """
    # when·then: 정수가 아니거나 0 이하이거나 범위를 넘으면 ValidationError다
    with pytest.raises(ValidationError):
        DealActionSearchParams(**{field: bad})


@pytest.mark.parametrize("field", ["actor_user_id", "action_type_id"])
def test_id_query_parameters_arrive_as_text_and_become_integers(field: str) -> None:
    """id 파라미터는 문자열로 와서 정수로 바뀐다.

    테스트 코드: NA-036
    """
    # when: 문자열 "5"를 조회 조건으로 바꾼다
    query = DealActionSearchParams.model_validate({field: "5"}).to_query("20261016-A001")
    # then: 정수 5다
    assert getattr(query, field) == 5


@pytest.mark.parametrize(
    "params",
    [
        {"offset": 0},
        {"limit": 10},
        {"deal_code": "20261016-A001"},
        {"actor": "박영업"},
        {"unknown": "x"},
        {"actor_user_id": "not-an-id"},
        {"action_type": "meeting"},  # 구 파라미터(enum 값)는 모르는 파라미터다
        {"action_type_id": "not-an-id"},
        {"acted_from": "soon"},
        {"due_to": "2026-13-40"},
    ],
)
def test_invalid_or_retired_search_params_are_rejected(params: dict[str, Any]) -> None:
    """모르는·폐지된 파라미터와 형식이 틀린 id·날짜는 요청 형식 오류다.

    테스트 코드: NA-036
    """
    # when·then: 폐지된 파라미터·모르는 이름·틀린 id·틀린 날짜는 ValidationError다
    with pytest.raises(ValidationError):
        DealActionSearchParams(**params)


def test_keyword_of_one_hundred_is_accepted_and_one_hundred_one_is_rejected() -> None:
    """검색어 100자는 받아들이고 101자는 요청 형식 오류다.

    테스트 코드: NA-028
    """
    # when: 100자 검색어를 조회 조건으로 바꾼다
    accepted = DealActionSearchParams(keyword="가" * 100).to_query("20261016-A001")
    # then: 그대로 받아들인다
    assert accepted.keyword == "가" * 100
    # when·then: 101자 검색어는 ValidationError다
    with pytest.raises(ValidationError):
        DealActionSearchParams(keyword="가" * 101)


def test_a_malformed_deal_code_in_the_path_is_a_not_found() -> None:
    """형식이 틀린 Deal code는 없는 Deal과 같은 DealNotFoundError다.

    테스트 코드: NA-021
    """
    # when·then: 형식이 틀린 code로 조회 조건을 만들면 DealNotFoundError다
    with pytest.raises(DealNotFoundError):
        DealActionSearchParams().to_query("not-a-code")


def test_malformed_code_is_not_found_before_a_reversed_range_is_checked() -> None:
    """형식이 틀린 code는 범위 오류보다 먼저 404이고, 형식이 맞는 code는 범위 422가 된다.

    테스트 코드: NA-037
    """
    # given: 거꾸로 된 수행일 범위의 파라미터
    params = DealActionSearchParams(acted_from="2027-05-21", acted_to="2027-05-20")
    # when·then: 형식이 틀린 code는 DealNotFoundError(404)다
    with pytest.raises(DealNotFoundError):
        params.to_query("not-a-code")
    # when·then: 형식은 맞지만 없는 code는 Deal 존재 확인 전에 수행일 범위 InvalidValueError(422)다
    with raises_with(InvalidValueError, "수행일 범위의 시작은 끝보다 늦을 수 없습니다."):
        params.to_query("20261016-ZZZZ")
