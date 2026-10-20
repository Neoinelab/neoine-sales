"""Feature: 영업은 Action을 남기며 Status와 Forecast를 한 번에 바꾼다.

`status_changes`는 적용 순서대로 최대 2개이고, 두 번째는 첫 변경 적용 후 상태로 판정한다. 하나라도
실패하면 Action·Deal·History 모두 그대로다. 기존 단일 `status_change`는 그대로 동작한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import (
    SUMMARY_WITH_MEMO,
    action_body,
    then_body_has,
    then_deal_has_no_actions,
    then_detail_is,
    when_register_action_with_body,
    when_update_action_with_body,
)
from tests.functional.steps.actions import given_action as _given_action
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_changes import CHOICE_REQUIRED, CLOSING
from tests.functional.steps.deals import given_deal, then_deal_keeps, then_history_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ACTION_ROW = ("action", "Action", "", f"등록: {SUMMARY_WITH_MEMO}")
SYNC_CONFLICT = "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요."


def _change(
    field: str, value: str, resolution: dict[str, object] | None = None
) -> dict[str, object]:
    item: dict[str, object] = {"change": {"field": field, "value": value}}
    if resolution is not None:
        item["resolution"] = resolution
    return item


async def test_status_and_forecast_change_with_one_action(api: Api) -> None:
    """Scenario: Status와 Forecast를 한 Action으로 바꾸면 둘 다 바뀌고 이력은 변경 순서다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    body = action_body(
        status_changes=[_change("status_key", "introduction"), _change("forecast_key", "best")]
    )
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_status_is(response, 201)
    then_body_has(response, status_key="introduction", forecast_key="best")
    await then_deal_keeps(api, deal["code"], status_key="introduction", forecast_key="best")
    await then_history_is(
        api,
        deal["code"],
        [
            ("status", "Status", "기회발굴", "제품소개"),
            ("forecast", "Forecast", "Pipeline", "Best"),
            ACTION_ROW,
        ],
    )


async def test_reopening_and_moving_the_status_in_one_action(api: Api) -> None:
    """Scenario: Won Deal을 Forecast로 되돌리고 같은 Action에서 Status를 옮길 수 있다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(
        api,
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date="2026-09-01",
    )
    body = action_body(
        status_changes=[
            _change("forecast_key", "commit", {"status_key": "poc_completed"}),
            _change("status_key", "introduction"),
        ]
    )
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_status_is(response, 201)
    then_body_has(response, status_key="introduction", forecast_key="commit")
    await then_deal_keeps(api, deal["code"], status_key="introduction", forecast_key="commit")


async def test_a_conflicting_pair_is_rejected_and_nothing_changes(api: Api) -> None:
    """Scenario: 두 번째 변경이 첫 변경의 값을 뒤집으면 422이고 아무것도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    body = action_body(
        status_changes=[
            _change("status_key", "introduction"),
            _change("forecast_key", "won", CLOSING),
        ]
    )
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, SYNC_CONFLICT)
    await then_deal_has_no_actions(api, deal["code"])
    await then_deal_keeps(api, deal["code"], status_key="prospecting", forecast_key="pipeline")
    await then_history_is(api, deal["code"], [])


async def test_a_failing_second_change_keeps_the_first_unsaved(api: Api) -> None:
    """Scenario: 두 번째 변경에 필요한 선택이 없으면 422이고 첫 변경도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="prospecting", forecast_key="lost")
    body = action_body(
        status_changes=[_change("status_key", "introduction"), _change("forecast_key", "commit")]
    )
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, CHOICE_REQUIRED)
    await then_deal_has_no_actions(api, deal["code"])
    await then_deal_keeps(api, deal["code"], status_key="prospecting", forecast_key="lost")
    await then_history_is(api, deal["code"], [])


_STATUS = _change("status_key", "introduction")
_FORECAST = _change("forecast_key", "best")


@pytest.mark.parametrize(
    "extra",
    [
        {"status_changes": [_STATUS, _change("status_key", "poc_completed")]},
        {"status_changes": [_STATUS, _FORECAST, _change("status_key", "poc_completed")]},
        {"status_change": _STATUS, "status_changes": [_FORECAST]},
    ],
    ids=["duplicate-field", "three-items", "both-forms"],
)
async def test_malformed_status_changes_are_request_validation_errors(
    api: Api, extra: dict[str, object]
) -> None:
    """Scenario: 같은 field 중복, 3개, 두 형태 동시 사용은 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(api, deal["code"], action_body(**extra))
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_deal_has_no_actions(api, deal["code"])


async def test_editing_an_action_does_not_accept_status_changes(api: Api) -> None:
    """Scenario: Action 수정 본문에 status_changes를 보내면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await _given_action(api, deal["code"])
    body = action_body(status_changes=[_STATUS])
    # When
    response = await when_update_action_with_body(api, created["id"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
