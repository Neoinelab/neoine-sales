"""Feature: Owner는 재직 영업 담당자만, Status와 Forecast는 폼 저장에서 함께 맞아야 한다.

Owner를 보내면 같은 값이어도 항상 검사하므로 퇴사한 Owner의 Deal은 Owner를 바꿔야 폼 저장이 된다
(보내지 않으면 검사하지 않는다). 종결(계약완료·Won)과 되돌림은 두 값을 함께 보내야 하고, 종결 후에도
수정할 수 있으며 되돌려도 금액·매출일은 그대로다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    OWNER_NOT_SALES,
    OWNER_RESIGNED,
    SYNC_MISMATCH,
    given_deal,
    given_my_user_id,
    then_deal_keeps,
    then_history_is,
    when_update_deal,
)
from tests.functional.steps.users import id_of, log_in, when_delete_user

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _deal_of_a_resigned_owner(api: Api) -> tuple[dict[str, object], int, int]:
    """park가 Owner인 Deal을 만들고 park를 퇴사시킨 뒤 다른 영업(sales-user)으로 로그인한다."""
    await given_logged_in_as(api, role="sales", login_id="park")
    park_id = await given_my_user_id(api)
    deal = await given_deal(api)
    await given_logged_in_as(api, role="admin")
    response = await when_delete_user(api, await id_of(api, "park"))
    assert response.json() == {"outcome": "resigned"}, response.text
    await given_logged_in_as(api, role="sales")
    return deal, park_id, await given_my_user_id(api)


async def test_a_resigned_owner_that_is_sent_again_is_rejected(api: Api) -> None:
    """Scenario: 퇴사한 Owner를 같은 값으로 다시 보내면 전용 문구의 422이다."""
    # Given
    deal, park_id, _ = await _deal_of_a_resigned_owner(api)
    # When
    response = await when_update_deal(api, str(deal["code"]), owner_user_id=park_id)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == OWNER_RESIGNED


async def test_an_owner_that_is_not_sent_is_not_checked(api: Api) -> None:
    """Scenario: Owner를 보내지 않으면 퇴사한 Owner여도 다른 필드는 수정할 수 있다."""
    # Given
    deal, park_id, _ = await _deal_of_a_resigned_owner(api)
    # When
    response = await when_update_deal(api, str(deal["code"]), name="이름만 수정")
    # Then
    then_status_is(response, 200)
    assert response.json()["owner"]["id"] == park_id
    assert response.json()["owner"]["resigned"] is True


async def test_replacing_a_resigned_owner_with_an_active_sales_user_is_logged(api: Api) -> None:
    """Scenario: 퇴사한 Owner를 재직 영업으로 바꾸면 이력에 '이름(퇴사)'이 남는다."""
    # Given
    deal, _, my_id = await _deal_of_a_resigned_owner(api)
    # When
    response = await when_update_deal(api, str(deal["code"]), owner_user_id=my_id)
    # Then
    then_status_is(response, 200)
    assert response.json()["owner"]["id"] == my_id
    await then_history_is(
        api, str(deal["code"]), [("owner", "Owner", "사용자 park(퇴사)", "사용자 sales-user")]
    )


async def test_an_admin_cannot_become_the_owner(api: Api) -> None:
    """Scenario: admin을 Owner로 바꾸려 하면 422이고 Owner는 그대로다."""
    # Given
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    admin_id = await given_user_registered(api, login_id="boss", role="admin")
    await log_in(api, login_id)
    # When
    response = await when_update_deal(api, deal["code"], owner_user_id=admin_id)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == OWNER_NOT_SALES
    await then_deal_keeps(api, deal["code"], owner_user_id=deal["owner_user_id"])


@pytest.mark.parametrize(
    "patch",
    [{"status_key": "contract_completed"}, {"forecast_key": "won"}],
)
async def test_closing_with_only_one_of_the_two_values_is_rejected(
    api: Api, patch: dict[str, str]
) -> None:
    """Scenario: 계약완료/Won 중 한 쪽만 보내면 동기화 문구의 422이고 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(api, deal["code"], **patch)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SYNC_MISMATCH
    await then_deal_keeps(api, deal["code"], status_key="prospecting", forecast_key="pipeline")


async def test_closing_with_both_values_is_logged_without_a_co_change_note(api: Api) -> None:
    """Scenario: 두 값을 함께 보내면 종결되고 Status·Forecast 이력이 각각 남는다(폼 저장)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(
        api, deal["code"], status_key="contract_completed", forecast_key="won"
    )
    # Then
    then_status_is(response, 200)
    await then_history_is(
        api,
        deal["code"],
        [
            ("status", "Status", "기회발굴", "계약완료"),
            ("forecast", "Forecast", "Pipeline", "Won"),
        ],
    )


async def test_a_closed_deal_can_be_edited_and_reopened_keeping_amount_and_date(api: Api) -> None:
    """Scenario: 종결 후에도 수정되고, 되돌려도 금액·Expected Close는 그대로다(잠금 없음)."""
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
    edited = await when_update_deal(api, deal["code"], name="종결 후 수정")
    reopened = await when_update_deal(
        api, deal["code"], status_key="price_negotiation", forecast_key="commit"
    )
    # Then
    then_status_is(edited, 200)
    then_status_is(reopened, 200)
    body = reopened.json()
    assert (body["revenue_amount"], body["revenue_date"]) == (777, "2026-09-01")
    assert (body["status_key"], body["forecast_key"]) == ("price_negotiation", "commit")
