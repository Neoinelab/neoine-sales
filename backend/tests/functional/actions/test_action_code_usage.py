"""Feature: Action이 스냅숏으로 가진 Status/Forecast 코드도 사용 중이라 admin이 지울 수 없다.

Deal은 쓰지 않고 Action 스냅숏만 쓰는 코드를 지우면 409이고 문구에 Action 건수가 들어간다. Deal도
쓰면 Deal 건수 문구가 먼저다. 코드 사용 수(usage_count)는 지금처럼 Deal 수만 센다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import (
    given_action,
    then_detail_is,
    when_delete_action,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import (
    given_code_id,
    then_code_exists,
    then_code_is_gone,
    then_usage_counts_are,
    when_delete_code,
    when_list_code_usage,
)
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_changes import when_change_deal
from tests.functional.steps.deals import given_deal

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ONLY_ACTION = "사용 중인 코드는 삭제할 수 없습니다. (Action 1건)"
DEAL_FIRST = "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"


async def _action_snapshot_of(api: Api, *, field: str, value: str) -> dict[str, object]:
    """sales가 Deal을 field=value 상태로 두고 Action을 남긴 뒤, Deal은 다른 값으로 옮겼다."""
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, **{field: value})
    created = await given_action(api, deal["code"])
    other = {"status_key": "technical_evaluation", "forecast_key": "commit"}[field]
    await when_change_deal(api, deal["code"], field, other)
    return created


@pytest.mark.parametrize(
    ("kind", "field", "value"),
    [
        pytest.param("status", "status_key", "introduction", id="status"),
        pytest.param("forecast", "forecast_key", "best", id="forecast"),
    ],
)
async def test_code_used_only_by_actions_cannot_be_deleted(
    api: Api, kind: str, field: str, value: str
) -> None:
    """Scenario: Deal은 안 쓰고 Action 스냅숏만 쓰는 코드의 삭제는 409(Action 건수)다."""
    # Given
    await _action_snapshot_of(api, field=field, value=value)
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind=kind, key=value)  # type: ignore[arg-type]
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, ONLY_ACTION)
    await then_code_exists(api, kind=kind, key=value)  # type: ignore[arg-type]


async def test_code_used_by_a_deal_and_an_action_reports_the_deal_count_first(api: Api) -> None:
    """Scenario: Deal도 쓰는 코드는 Action도 쓰더라도 Deal 건수 문구가 먼저다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="introduction")
    await given_action(api, deal["code"])
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, DEAL_FIRST)


async def test_usage_count_of_a_code_counts_deals_only(api: Api) -> None:
    """Scenario: 코드 사용 수는 Action 스냅숏을 세지 않고 Deal 수만 센다."""
    # Given
    await _action_snapshot_of(api, field="status_key", value="introduction")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_list_code_usage(api, kind="status")
    # Then
    then_status_is(response, 200)
    then_usage_counts_are(response, {"technical_evaluation": 1})


async def test_the_code_can_be_deleted_once_its_last_action_is_gone(api: Api) -> None:
    """Scenario: 그 코드를 쓰던 마지막 Action이 지워지면 코드를 삭제할 수 있다."""
    # Given
    created = await _action_snapshot_of(api, field="status_key", value="introduction")
    await given_logged_in_as(api, role="admin")
    await when_delete_action(api, str(created["id"]))
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_status_is(response, 204)
    await then_code_is_gone(api, kind="status", key="introduction")
