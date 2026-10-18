"""Feature: Deal이 현재 Status에 들어온 시각을 기록한다(Status key가 실제로 바뀔 때만 갱신).

등록 시각이 첫 진입이다. 폼 저장, 단일 변경(/changes, Forecast Won으로 함께 바뀌는 계약완료 포함),
Action 등록의 status_change가 Status key를 바꾸면 그 요청의 서버 시각이 새 진입 시각이다.
Forecast만, 다른 필드만, 같은 Status 값을 다시 보내는 변경은 진입 시각을 바꾸지 않는다.
응답 필드(`status_changed_at`, `status_days`)는 R2다. 여기서는 저장된 값을 확인한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import action_body, when_register_action_with_body
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deal_changes import CLOSING, when_change_deal
from tests.functional.steps.deal_risk import given_days_pass
from tests.functional.steps.deals import given_deal, when_update_deal
from tests.functional.steps.status_entry import (
    status_changed_at_of,
    then_status_entered_at_registration,
    then_status_entered_now,
    then_status_entry_is_unchanged,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_registration_records_the_first_entry(api: Api) -> None:
    """Scenario: 등록하면 진입 시각이 등록 시각이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    deal = await given_deal(api, status_key="introduction", forecast_key="best")
    # Then
    await then_status_entered_at_registration(api, deal["code"], api.clock.now())


async def test_a_form_save_that_changes_the_status_moves_the_entry(api: Api) -> None:
    """Scenario: PATCH로 Status가 바뀌면 진입 시각이 그 요청의 서버 시각이 된다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="prospecting")
    await given_days_pass(api, 5, login_id=login)
    # When
    response = await when_update_deal(api, deal["code"], status_key="introduction")
    # Then
    then_status_is(response, 200)
    await then_status_entered_now(api, deal["code"])


async def test_a_single_change_of_the_status_moves_the_entry(api: Api) -> None:
    """Scenario: /changes로 Status를 바꾸면 진입 시각이 그 요청의 서버 시각이 된다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="prospecting")
    await given_days_pass(api, 5, login_id=login)
    # When
    response = await when_change_deal(api, deal["code"], "status_key", "introduction")
    # Then
    then_status_is(response, 200)
    await then_status_entered_now(api, deal["code"])


async def test_closing_through_forecast_won_moves_the_entry_with_the_status(api: Api) -> None:
    """Scenario: Forecast를 Won으로 바꿔 Status가 계약완료로 함께 바뀌면 진입으로 본다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 5, login_id=login)
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "won", CLOSING)
    # Then
    then_status_is(response, 200)
    await then_status_entered_now(api, deal["code"])


async def test_an_action_that_changes_the_status_moves_the_entry(api: Api) -> None:
    """Scenario: Action 등록의 status_change가 Status를 바꾸면 진입 시각이 Action 등록 시각이다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="prospecting")
    await given_days_pass(api, 5, login_id=login)
    body = action_body(status_change={"change": {"field": "status_key", "value": "introduction"}})
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_status_is(response, 201)
    await then_status_entered_now(api, deal["code"])


@pytest.mark.parametrize(
    "patch",
    [
        {"forecast_key": "best"},
        {"name": "다른 이름"},
        {"status_key": "prospecting", "name": "같은 Status를 다시 보냄"},
    ],
    ids=["forecast-only", "other-field", "same-status-resent"],
)
async def test_changes_that_keep_the_status_do_not_move_the_entry(
    api: Api, patch: dict[str, object]
) -> None:
    """Scenario: Forecast만·다른 필드만·같은 Status 재전송은 진입 시각을 바꾸지 않는다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="prospecting")
    before = await status_changed_at_of(api, deal["code"])
    await given_days_pass(api, 5, login_id=login)
    # When
    response = await when_update_deal(api, deal["code"], **patch)
    # Then
    then_status_is(response, 200)
    await then_status_entry_is_unchanged(api, deal["code"], before)


async def test_an_action_without_a_status_change_does_not_move_the_entry(api: Api) -> None:
    """Scenario: status_change 없는 Action 등록은 진입 시각을 바꾸지 않는다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    before = await status_changed_at_of(api, deal["code"])
    await given_days_pass(api, 5, login_id=login)
    # When
    response = await when_register_action_with_body(api, deal["code"], action_body())
    # Then
    then_status_is(response, 201)
    await then_status_entry_is_unchanged(api, deal["code"], before)
