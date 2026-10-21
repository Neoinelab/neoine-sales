"""Feature: 수행 일시가 같은 Action은 등록한 순서(id 오름차순)로 나온다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action_at, when_list_actions
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import given_deal

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("sort", ["acted_at_asc", "acted_at_desc"])
async def test_actions_recorded_at_the_same_moment_are_listed_in_registration_order(
    api: Api, sort: str
) -> None:
    """Scenario: 같은 수행 일시의 Action 2건은 어느 acted_at 정렬이든 먼저 등록한 것이 앞이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    moment = api.clock.now()
    first = await given_action_at(api, deal["code"], moment, action="먼저 등록")
    second = await given_action_at(api, deal["code"], moment, action="나중 등록")
    # When
    response = await when_list_actions(api, deal["code"], sort=sort)
    # Then
    then_status_is(response, 200)
    items = response.json()["items"]
    assert first["acted_at"] == second["acted_at"]
    assert [item["id"] for item in items] == [first["id"], second["id"]]
    assert first["id"] < second["id"]
