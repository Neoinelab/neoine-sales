"""Action 검색 쿼리 파라미터(AC-18): 조건 매핑, 정렬 3종, 상태 필터, 거절되는 파라미터."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.ports.deal_action_repository import (
    DealActionQuery,
    DealActionSort,
    NextActionStatusFilter,
)
from app.domain.deal.errors import DealNotFoundError
from app.web.schemas.deal_action import DealActionSearchParams
from tests.factories import make_deal_code
from tests.support.ids import new_id
from tests.support.user_ids import uid


def test_search_params_default_to_everything_sorted_latest_first() -> None:
    query = DealActionSearchParams().to_query("20261016-A001")

    assert query == DealActionQuery(deal_code=make_deal_code("A001"))
    assert query.sort is DealActionSort.ACTED_AT_DESC


def test_search_params_map_every_condition() -> None:
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

    query = params.to_query("20261016-A001")

    assert query.deal_code == make_deal_code("A001")
    assert query.action_type_id == email_id
    assert query.actor_user_id == uid("kim")
    assert query.keyword == "견적"
    assert (query.acted_from, query.acted_to) == (date(2026, 10, 1), date(2026, 10, 31))
    assert (query.due_from, query.due_to) == (date(2026, 11, 1), date(2026, 11, 30))
    assert query.sort is DealActionSort.DUE_DATE_ASC


@pytest.mark.parametrize("value", ["open", "done", "not_done", "closed"])
def test_search_params_pass_the_next_action_status_filter(value: str) -> None:
    query = DealActionSearchParams(next_action_status=value).to_query("20261016-A001")

    assert query.next_action_status == NextActionStatusFilter(value)


def test_search_params_default_to_no_status_filter() -> None:
    assert DealActionSearchParams().to_query("20261016-A001").next_action_status is None


@pytest.mark.parametrize("value", ["notDone", "DONE", "all", "", "close"])
def test_any_other_status_filter_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        DealActionSearchParams(next_action_status=value)


@pytest.mark.parametrize("sort", ["acted_at_desc", "acted_at_asc", "due_date_asc"])
def test_the_three_sorts_are_accepted(sort: str) -> None:
    assert DealActionSearchParams(sort=sort).sort.value == sort


@pytest.mark.parametrize("sort", ["due_date_desc", "created_asc", "DUE_DATE_ASC", ""])
def test_any_other_sort_is_rejected(sort: str) -> None:
    with pytest.raises(ValidationError):
        DealActionSearchParams(sort=sort)


@pytest.mark.parametrize("field", ["actor_user_id", "action_type_id"])
@pytest.mark.parametrize("bad", ["abc", "1.5", "0", "-1", 0, -1, 2**53, "9007199254740992"])
def test_id_query_parameters_must_be_positive_integers(field: str, bad: object) -> None:
    with pytest.raises(ValidationError):
        DealActionSearchParams(**{field: bad})


@pytest.mark.parametrize("field", ["actor_user_id", "action_type_id"])
def test_id_query_parameters_arrive_as_text_and_become_integers(field: str) -> None:
    query = DealActionSearchParams.model_validate({field: "5"}).to_query("20261016-A001")

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
        {"keyword": "가" * 101},
    ],
)
def test_invalid_or_retired_search_params_are_rejected(params: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DealActionSearchParams(**params)


def test_a_malformed_deal_code_in_the_path_is_a_not_found() -> None:
    with pytest.raises(DealNotFoundError):
        DealActionSearchParams().to_query("not-a-code")
