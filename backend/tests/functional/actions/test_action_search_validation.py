"""Feature: Action 검색은 잘못된 조건을 거절하고, 폐지된 전역 검색은 없다.

범위가 거꾸로면 422(범위 종류를 알려 주는 문구), 모르는·폐지된 쿼리와 잘못된 값은 422
request-validation이다. 없는 Deal의 목록은 404이고, 전역 검색(GET /deal-actions)은 404다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import names_of, then_detail_is
from tests.functional.steps.actions import (
    REVERSED_ACTED,
    REVERSED_DUE,
    given_many_actions,
    when_list_actions,
    when_search_all_actions,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import NOT_FOUND, given_deal

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        pytest.param({"acted_from": "2027-05-21", "acted_to": "2027-05-20"}, REVERSED_ACTED),
        pytest.param({"due_from": "2027-04-10", "due_to": "2027-04-01"}, REVERSED_DUE),
    ],
)
async def test_reversed_range_is_rejected(api: Api, params: dict[str, str], detail: str) -> None:
    """Scenario: 시작이 끝보다 늦은 범위는 422이고 문구가 범위 종류를 알려 준다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_list_actions(api, deal["code"], **params)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, detail)


async def test_equal_range_bounds_are_allowed(api: Api) -> None:
    """Scenario: 시작과 끝이 같은 범위는 허용된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_list_actions(
        api,
        deal["code"],
        acted_from="2027-05-20",
        acted_to="2027-05-20",
        due_from="2027-04-01",
        due_to="2027-04-01",
    )
    # Then
    then_status_is(response, 200)


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"sort": "due_date_desc"}, id="retired-sort"),
        pytest.param({"sort": "created_asc"}, id="unknown-sort"),
        pytest.param({"sort": "DUE_DATE_ASC"}, id="sort-is-case-sensitive"),
        pytest.param({"offset": 0}, id="offset-is-gone"),
        pytest.param({"limit": 10}, id="limit-is-gone"),
        pytest.param({"deal_code": "20261016-A001"}, id="deal-code-is-in-the-path"),
        pytest.param({"action_type": "meeting"}, id="retired-action-type-enum"),
        pytest.param({"action_type_id": "not-a-uuid"}, id="bad-action-type-id"),
        pytest.param({"actor_user_id": "not-a-uuid"}, id="bad-actor-id"),
        pytest.param({"actor": "박영업"}, id="free-text-actor"),
        pytest.param({"keyword": "가" * 101}, id="keyword-over-100"),
        pytest.param({"due_from": "2027-13-40"}, id="bad-date"),
        pytest.param({"unknown": "x"}, id="unknown-param"),
    ],
)
async def test_invalid_or_retired_search_params_are_rejected(
    api: Api, params: dict[str, str | int]
) -> None:
    """Scenario: 모르는 쿼리·폐지된 쿼리·잘못된 값은 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_list_actions(api, deal["code"], **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_keyword_with_a_nul_character_is_an_invalid_value_not_a_server_error(
    api: Api,
) -> None:
    """Scenario: 검색어의 NUL 문자는 500이 아니라 422 invalid-value다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_list_actions(api, deal["code"], keyword="a\x00b")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


async def test_all_actions_are_returned_without_paging(api: Api) -> None:
    """Scenario: Action이 25건이어도 페이지 없이 전부 돌려준다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_many_actions(api, deal["code"], 25)
    # When
    response = await when_list_actions(api, deal["code"])
    # Then
    then_status_is(response, 200)
    assert len(names_of(response)) == 25
    assert set(response.json()) == {"items"}


@pytest.mark.parametrize("code", ["20260101-ZZZZ", "not-a-code"])
async def test_listing_a_missing_or_malformed_deal_is_not_found(api: Api, code: str) -> None:
    """Scenario: 없는 Deal이나 형식이 틀린 code의 Action 목록은 404다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_actions(api, code)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, NOT_FOUND)


async def test_global_action_search_is_gone(api: Api) -> None:
    """Scenario: 전역 Action 검색(GET /deal-actions)은 폐지되어 404다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_search_all_actions(api)
    # Then
    then_status_is(response, 404)
