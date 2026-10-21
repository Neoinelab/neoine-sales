"""Feature: Action의 경로 id는 1 이상 2^53-1 이하의 정수다. 형식이 틀리면 422, 없는 id는 404다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import (
    when_delete_action,
    when_get_action,
    when_update_action,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is
from tests.support.ids import MAX_ID, MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

MALFORMED = ["abc", "1.5", "0", "-1", str(MAX_ID + 1), "9223372036854775808"]


@pytest.mark.parametrize("action_id", MALFORMED)
async def test_user_gets_a_validation_error_for_a_malformed_action_id(
    api: Api, action_id: str
) -> None:
    """Scenario: 정수가 아니거나 0·음수·상한 초과인 Action id는 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    read = await when_get_action(api, action_id)
    update = await when_update_action(api, action_id)
    delete = await when_delete_action(api, action_id)
    # Then
    for response in (read, update, delete):
        then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("action_id", [MISSING_ID, MAX_ID])
async def test_user_gets_not_found_for_a_well_formed_action_id_that_does_not_exist(
    api: Api, action_id: int
) -> None:
    """Scenario: 형식이 맞는 없는 Action id는 상한 값이어도 404 not-found다(500이 아니다)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_action(api, action_id)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
