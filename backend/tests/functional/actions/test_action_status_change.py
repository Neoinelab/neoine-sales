"""Feature: 영업은 Action을 남기며 Status/Forecast를 함께 바꾸고, 스냅숏은 그 뒤에도 변하지 않는다.

P1 단일 변경(applyChange)과 같은 동기화 규칙을 한 요청에서 적용한다. 검증이 실패하면 Action·Deal·
History 모두 그대로이고, 성공하면 Action에는 변경 후 값이 스냅숏으로 남는다. History는 Deal 변경
건이 먼저, Action 등록 건이 나중에 저장돼 목록에서는 Action 건이 맨 위다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import (
    SUMMARY_WITH_MEMO,
    action_body,
    same_instant,
    then_acted_at_is_the_server_time,
    then_body_has,
    then_deal_has_no_actions,
    then_detail_is,
    when_get_action,
    when_register_action_with_body,
    when_update_action,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_changes import (
    CHOICE_REQUIRED,
    CLOSING,
    REVENUE_REQUIRED,
    UNKNOWN_CODE,
    when_change_deal,
)
from tests.functional.steps.deals import (
    given_deal,
    then_deal_keeps,
    then_history_is,
    when_get_deal,
    when_list_history,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ACTION_ROW = ("action", "Action", "", f"등록: {SUMMARY_WITH_MEMO}")


def _body(field: str, value: str, resolution: dict[str, object] | None = None) -> dict[str, object]:
    status_change: dict[str, object] = {"change": {"field": field, "value": value}}
    if resolution is not None:
        status_change["resolution"] = resolution
    return action_body(status_change=status_change)


async def test_closing_with_an_action_requires_actual_revenue(api: Api) -> None:
    """Scenario: 계약완료로 바꾸며 Action을 남기려면 매출금액·매출일이 필요하고 없으면 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], _body("status_key", "contract_completed")
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, REVENUE_REQUIRED)
    await then_deal_has_no_actions(api, deal["code"])
    await then_deal_keeps(api, deal["code"], status_key="prospecting", forecast_key="pipeline")
    await then_history_is(api, deal["code"], [])


async def test_status_and_action_are_saved_together(api: Api) -> None:
    """Scenario: 계약완료로 Action을 남기면 Deal이 바뀌고 Action에는 변경 후 값이 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], _body("status_key", "contract_completed", CLOSING)
    )
    # Then
    then_status_is(response, 201)
    then_acted_at_is_the_server_time(response)
    then_body_has(response, status_key="contract_completed", forecast_key="won")
    await then_deal_keeps(
        api,
        deal["code"],
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=900_000_000,
        revenue_date="2026-10-20",
    )
    await then_history_is(
        api,
        deal["code"],
        [
            ("status", "Status", "기회발굴", "계약완료"),
            ("forecast", "Forecast", "Pipeline", "Won (Status 계약완료와 함께 변경)"),
            ("amount", "금액", "150,000,000원", "900,000,000원"),
            ("expectedClose", "Expected Close", "2026-06-30", "2026-10-20"),
            ACTION_ROW,
        ],
    )
    newest = (await when_list_history(api, deal["code"])).json()[0]
    assert newest["category"] == "action"


async def test_deal_updated_at_follows_the_combined_change(api: Api) -> None:
    """Scenario: Status가 실제로 바뀌면 Deal의 수정 시각이 Action의 수행 시각으로 갱신된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], _body("forecast_key", "best")
    )
    # Then
    then_status_is(response, 201)
    await then_deal_keeps(api, deal["code"], forecast_key="best", status_key="prospecting")
    detail = (await when_get_deal(api, deal["code"])).json()
    assert same_instant(detail["updated_at"], response.json()["acted_at"])


async def test_forecast_can_be_changed_with_an_action(api: Api) -> None:
    """Scenario: Forecast만 바꿔도 되고 Status는 그대로이며 스냅숏은 변경 후 값이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], _body("forecast_key", "lost")
    )
    # Then
    then_status_is(response, 201)
    then_body_has(response, status_key="prospecting", forecast_key="lost")
    await then_history_is(
        api, deal["code"], [("forecast", "Forecast", "Pipeline", "Lost"), ACTION_ROW]
    )


async def test_failed_status_change_saves_no_action(api: Api) -> None:
    """Scenario: 없는 코드로 바꾸려 하면 422이고 Action·Deal·History 모두 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], _body("status_key", "no_such_status")
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, UNKNOWN_CODE)
    await then_deal_has_no_actions(api, deal["code"])
    await then_history_is(api, deal["code"], [])


async def test_reopening_a_won_deal_with_an_action_needs_a_choice(api: Api) -> None:
    """Scenario: 종결 Deal을 되돌리려면 함께 둘 값을 골라야 하고 고르지 않으면 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(
        api,
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date="2026-09-01",
    )
    # When
    response = await when_register_action_with_body(
        api, deal["code"], _body("forecast_key", "commit")
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, CHOICE_REQUIRED)
    await then_deal_has_no_actions(api, deal["code"])
    await then_deal_keeps(api, deal["code"], status_key="contract_completed", forecast_key="won")


async def test_the_same_status_leaves_the_deal_unchanged(api: Api) -> None:
    """Scenario: 현재 값과 같은 값으로 바꾸면 Deal은 그대로이고 Action만 현재 값으로 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], _body("status_key", "prospecting")
    )
    # Then
    then_status_is(response, 201)
    then_body_has(response, status_key="prospecting", forecast_key="pipeline")
    assert same_instant(
        (await when_get_deal(api, deal["code"])).json()["updated_at"], deal["updated_at"]
    )
    await then_history_is(api, deal["code"], [ACTION_ROW])


@pytest.mark.parametrize("field", ["revenue_amount", "revenue_date", "name"])
async def test_only_status_and_forecast_may_be_changed_with_an_action(api: Api, field: str) -> None:
    """Scenario: 매출금액·Expected Close 같은 다른 필드는 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], action_body(status_change={"change": {"field": field, "value": 1}})
    )
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_snapshot_does_not_follow_later_deal_changes(api: Api) -> None:
    """Scenario: Deal의 Status/Forecast가 나중에 바뀌어도 Action의 스냅숏은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = (await when_register_action_with_body(api, deal["code"], action_body())).json()
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "best")
    # Then
    then_status_is(response, 200)
    stored = (await when_get_action(api, created["id"])).json()
    assert (stored["status_key"], stored["forecast_key"]) == ("prospecting", "pipeline")


async def test_editing_an_action_does_not_change_its_snapshot(api: Api) -> None:
    """Scenario: Action을 고쳐도 Status/Forecast 스냅숏·수행 일시·담당자는 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = (
        await when_register_action_with_body(api, deal["code"], _body("forecast_key", "best"))
    ).json()
    await when_change_deal(api, deal["code"], "forecast_key", "commit")
    # When
    response = await when_update_action(api, created["id"], action="수정한 진행사항")
    # Then
    then_status_is(response, 200)
    then_body_has(
        response,
        action="수정한 진행사항",
        status_key="prospecting",
        forecast_key="best",
        actor=created["actor"],
    )
    assert same_instant(response.json()["acted_at"], created["acted_at"])
