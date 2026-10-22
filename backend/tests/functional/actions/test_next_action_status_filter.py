"""Feature: 영업은 Deal 상세에서 Next Action 상태로 Action을 거른다.

선택지는 open / done / not_done / closed(= done 또는 not_done)이다. 상태 필터가 있으면 Next Action이
없는 Action(상태 null)은 제외된다. 다른 조건과는 AND로 결합하고 허용하지 않는 값은 422다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import then_action_names_are
from tests.functional.steps.actions import given_action, when_list_actions
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.deals import given_deal
from tests.functional.steps.next_action_status import given_status_changed

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NEWEST_FIRST = ["진행만", "미수행", "수행", "열림"]


async def _deal_with_four_actions(api: Api) -> str:
    """오래된 순서: 열림(open) -> 수행(done) -> 미수행(not_done) -> 진행만(Next Action 없음)."""
    await given_logged_in_as(api, role="sales")
    code = str((await given_deal(api))["code"])
    await given_action(api, code, action="열림")
    done = await given_action(api, code, action="수행")
    not_done = await given_action(api, code, action="미수행")
    await given_action(api, code, action="진행만", next_action="")
    await given_status_changed(api, done["id"], "done")
    await given_status_changed(api, not_done["id"], "not_done")
    return code


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param("open", ["열림"], id="open"),
        pytest.param("done", ["수행"], id="done"),
        pytest.param("not_done", ["미수행"], id="not-done"),
        pytest.param("closed", ["미수행", "수행"], id="closed-is-done-or-not-done"),
    ],
)
async def test_status_filter_lists_only_that_status(
    api: Api, status: str, expected: list[str]
) -> None:
    """Scenario: 상태를 고르면 그 상태의 Action만 나오고 Next Action이 없는 Action은 빠진다."""
    # Given
    code = await _deal_with_four_actions(api)
    # When
    response = await when_list_actions(api, code, next_action_status=status)
    # Then
    then_action_names_are(response, expected)


async def test_without_a_status_filter_every_action_is_listed(api: Api) -> None:
    """Scenario: 상태 조건이 없으면 Next Action이 없는 Action도 포함해 모두 나온다."""
    # Given
    code = await _deal_with_four_actions(api)
    # When
    response = await when_list_actions(api, code)
    # Then
    then_action_names_are(response, NEWEST_FIRST)


async def test_status_filter_combines_with_the_other_conditions(api: Api) -> None:
    """Scenario: 상태 조건은 검색어와 AND로 결합된다."""
    # Given
    code = await _deal_with_four_actions(api)
    # When
    response = await when_list_actions(api, code, next_action_status="closed", keyword="미수행")
    # Then
    then_action_names_are(response, ["미수행"])


async def test_reopened_action_is_listed_as_open(api: Api) -> None:
    """Scenario: 종료했다가 Open으로 되돌린 Action은 open 필터에 나오고 closed에서는 빠진다."""
    # Given
    await given_logged_in_as(api, role="sales")
    code = str((await given_deal(api))["code"])
    created = await given_action(api, code, action="되돌림")
    await given_status_changed(api, created["id"], "done")
    await given_status_changed(api, created["id"], "open")
    # When
    opened = await when_list_actions(api, code, next_action_status="open")
    closed = await when_list_actions(api, code, next_action_status="closed")
    # Then
    then_action_names_are(opened, ["되돌림"])
    then_action_names_are(closed, [])


@pytest.mark.parametrize("value", ["notDone", "DONE", "all", "", "close"])
async def test_a_status_outside_the_allowed_values_is_rejected(api: Api, value: str) -> None:
    """Scenario: 허용하지 않는 상태 값은 422 request-validation이다."""
    # Given
    code = await _deal_with_four_actions(api)
    # When
    response = await when_list_actions(api, code, next_action_status=value)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        pytest.param("next_action_status_asc", ["열림", "수행", "미수행", "진행만"], id="asc"),
        pytest.param("next_action_status_desc", ["미수행", "수행", "열림", "진행만"], id="desc"),
    ],
)
async def test_status_sort_orders_open_done_not_done_with_no_status_last(
    api: Api, sort: str, expected: list[str]
) -> None:
    """Scenario: 상태 정렬은 Open, 수행, 미수행 순이고 상태 없음은 방향과 관계없이 맨 뒤다."""
    # Given
    code = await _deal_with_four_actions(api)
    # When
    response = await when_list_actions(api, code, sort=sort)
    # Then
    then_action_names_are(response, expected)
