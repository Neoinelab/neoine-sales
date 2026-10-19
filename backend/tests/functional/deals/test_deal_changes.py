"""Feature: 영업은 Status·Forecast를 함께 맞추며 Deal의 값을 하나씩 바꾼다.

계약완료/Won으로 바꾸면 두 값이 함께 바뀌고 실제 매출금액·매출일이 필요하다. 종결 Deal을 되돌리면
함께 둘 값을 골라야 한다. 서버는 어떤 값을 물을지 알려 주지 않고 답을 같은 규칙으로 재검증한다.
금액과 Expected Close는 각각 하나씩 바꾼다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_changes import (
    AMOUNT_INVALID,
    CHOICE_REQUIRED,
    CLOSING,
    CLOSING_NOTICE,
    REVENUE_REQUIRED,
    UNKNOWN_CODE,
    then_co_changed_is,
    then_notice_is,
    then_response_has_the_documented_keys,
    then_returned_deal_has,
    when_change_deal,
)
from tests.functional.steps.deals import (
    NOT_FOUND,
    given_deal,
    then_deal_keeps,
    then_history_is,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

WON_DEAL = {
    "status_key": "contract_completed",
    "forecast_key": "won",
    "revenue_amount": 777,
    "revenue_date": "2026-09-01",
}


async def test_closing_by_status_without_revenue_is_rejected_and_nothing_changes(api: Api) -> None:
    """Scenario: 계약완료로 바꾸면서 매출금액·매출일을 주지 않으면 422이고 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_change_deal(api, deal["code"], "status_key", "contract_completed")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == REVENUE_REQUIRED
    await then_deal_keeps(api, deal["code"], status_key="prospecting", forecast_key="pipeline")
    await then_history_is(api, deal["code"], [])


async def test_closing_by_status_changes_forecast_too_and_saves_the_revenue(api: Api) -> None:
    """Scenario: 계약완료로 바꾸면 Forecast가 Won으로 함께 바뀌고 매출금액·매출일이 저장된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_change_deal(
        api, deal["code"], "status_key", "contract_completed", CLOSING
    )
    # Then
    then_status_is(response, 200)
    then_response_has_the_documented_keys(response)
    then_returned_deal_has(
        response,
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=900_000_000,
        revenue_date="2026-10-20",
    )
    then_co_changed_is(response, [("forecast_key", "pipeline", "won")])
    then_notice_is(response, CLOSING_NOTICE)
    await then_history_is(
        api,
        deal["code"],
        [
            ("status", "Status", "기회발굴", "계약완료"),
            ("forecast", "Forecast", "Pipeline", "Won (Status 계약완료와 함께 변경)"),
            ("amount", "금액(단위:천원)", "150,000", "900,000"),
            ("expectedClose", "Expected Close", "2026-06-30", "2026-10-20"),
        ],
    )


async def test_closing_by_forecast_changes_status_too(api: Api) -> None:
    """Scenario: Won으로 바꾸면 Status가 계약완료로 함께 바뀌고 이력에 함께 변경이 표기된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "won", CLOSING)
    # Then
    then_status_is(response, 200)
    then_co_changed_is(response, [("status_key", "prospecting", "contract_completed")])
    then_notice_is(response, CLOSING_NOTICE)
    history = await api.get(f"/api/v1/deals/{deal['code']}/history")
    targets = {(e["target"], e["after"]) for e in history.json()}
    assert ("Status", "계약완료 (Forecast Won과 함께 변경)") in targets


async def test_reopening_a_won_deal_asks_for_a_status(api: Api) -> None:
    """Scenario: Won에서 다른 Forecast로 바꾸려면 Status를 골라야 하고 금액·매출일은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, **WON_DEAL)
    # When
    missing = await when_change_deal(api, deal["code"], "forecast_key", "commit")
    wrong = await when_change_deal(
        api, deal["code"], "forecast_key", "commit", {"status_key": "contract_completed"}
    )
    response = await when_change_deal(
        api, deal["code"], "forecast_key", "commit", {"status_key": "poc_completed"}
    )
    # Then
    for rejected in (missing, wrong):
        then_problem_is(rejected, status=422, type_suffix="invalid-value")
        assert rejected.json()["detail"] == CHOICE_REQUIRED
    then_status_is(response, 200)
    then_returned_deal_has(
        response,
        status_key="poc_completed",
        forecast_key="commit",
        revenue_amount=777,
        revenue_date="2026-09-01",
    )
    then_co_changed_is(response, [("status_key", "contract_completed", "poc_completed")])
    then_notice_is(response, "Status가 'POC완료'로 함께 변경되었습니다.")


async def test_moving_back_from_contract_completed_asks_for_a_forecast(api: Api) -> None:
    """Scenario: 계약완료에서 이전 단계로 바꾸려면 Won이 아닌 Forecast를 골라야 한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, **WON_DEAL)
    # When
    missing = await when_change_deal(api, deal["code"], "status_key", "poc_completed")
    still_won = await when_change_deal(
        api, deal["code"], "status_key", "poc_completed", {"forecast_key": "won"}
    )
    response = await when_change_deal(
        api, deal["code"], "status_key", "poc_completed", {"forecast_key": "best"}
    )
    # Then
    for rejected in (missing, still_won):
        then_problem_is(rejected, status=422, type_suffix="invalid-value")
        assert rejected.json()["detail"] == CHOICE_REQUIRED
    then_status_is(response, 200)
    then_returned_deal_has(response, status_key="poc_completed", forecast_key="best")
    then_co_changed_is(response, [("forecast_key", "won", "best")])
    then_notice_is(response, "Forecast가 'Best'로 함께 변경되었습니다.")


async def test_losing_keeps_the_status(api: Api) -> None:
    """Scenario: Won이 아닌 Deal을 Lost로 바꾸면 Status는 그대로이고 함께 바뀐 값이 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="price_negotiation")
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "lost")
    # Then
    then_status_is(response, 200)
    then_returned_deal_has(response, status_key="price_negotiation", forecast_key="lost")
    then_co_changed_is(response, [])
    then_notice_is(response, None)
    await then_history_is(api, deal["code"], [("forecast", "Forecast", "Pipeline", "Lost")])


async def test_the_same_value_changes_nothing(api: Api) -> None:
    """Scenario: 같은 값으로 바꾸면 200이고 이력과 수정 시각이 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    api.clock.advance(600)
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "pipeline")
    # Then
    then_status_is(response, 200)
    then_co_changed_is(response, [])
    then_notice_is(response, None)
    await then_history_is(api, deal["code"], [])
    await then_deal_keeps(api, deal["code"], updated_at=deal["updated_at"])


@pytest.mark.parametrize("field", ["status_key", "forecast_key"])
async def test_an_unknown_code_is_rejected(api: Api, field: str) -> None:
    """Scenario: 없는 Status·Forecast 코드로 바꾸면 422이고 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_change_deal(api, deal["code"], field, "no_such_code")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == UNKNOWN_CODE
    await then_deal_keeps(api, deal["code"], status_key="prospecting", forecast_key="pipeline")


async def test_a_sales_user_who_is_not_the_owner_may_change_the_deal(api: Api) -> None:
    """Scenario: Owner가 아닌 다른 영업도 값을 바꿀 수 있고 이력 변경자는 그 사용자다."""
    # Given
    await given_logged_in_as(api, role="sales", login_id="owner-sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="sales", login_id="other-sales")
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "best")
    # Then
    then_status_is(response, 200)
    history = await api.get(f"/api/v1/deals/{deal['code']}/history")
    assert history.json()[0]["by"]["name"] == "사용자 other-sales"


async def test_a_viewer_cannot_change_a_deal(api: Api) -> None:
    """Scenario: 조회 전용(user) 역할은 값을 바꿀 수 없다(403)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="user")
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "best")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")


async def test_an_anonymous_user_cannot_change_a_deal(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_out(api)
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "best")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


@pytest.mark.parametrize("code", ["20260101-ZZZZ", "not-a-code"])
async def test_an_unknown_or_malformed_code_is_not_found(api: Api, code: str) -> None:
    """Scenario: 없는 Deal이나 형식이 틀린 code는 404이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_change_deal(api, code, "forecast_key", "best")
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == NOT_FOUND


async def test_changing_the_amount_logs_the_formatted_amounts(api: Api) -> None:
    """Scenario: 금액을 바꾸면 이력에 '금액(단위:천원)' 대상과 '1,870,000' 형식으로 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_change_deal(api, deal["code"], "revenue_amount", 1_870_000_000)
    # Then
    then_status_is(response, 200)
    then_returned_deal_has(response, revenue_amount=1_870_000_000)
    then_co_changed_is(response, [])
    await then_history_is(
        api, deal["code"], [("amount", "금액(단위:천원)", "150,000", "1,870,000")]
    )


@pytest.mark.parametrize("amount", [0, -1, 2**53])
async def test_an_invalid_amount_is_rejected(api: Api, amount: int) -> None:
    """Scenario: 1 미만이거나 2^53 이상인 금액은 422이고 금액은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_change_deal(api, deal["code"], "revenue_amount", amount)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == AMOUNT_INVALID
    await then_deal_keeps(api, deal["code"], revenue_amount=150_000_000)


async def test_changing_the_expected_close_logs_the_dates(api: Api) -> None:
    """Scenario: Expected Close를 바꾸면 저장되고 이력에 YYYY-MM-DD로 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_change_deal(api, deal["code"], "revenue_date", "2026-12-31")
    # Then
    then_status_is(response, 200)
    then_returned_deal_has(response, revenue_date="2026-12-31")
    await then_history_is(
        api, deal["code"], [("expectedClose", "Expected Close", "2026-06-30", "2026-12-31")]
    )
