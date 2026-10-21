"""Feature: 잘못된 입력과 권한 없는 요청으로는 Deal이 등록되지 않는다.

입력 오류는 화면(목업)과 같은 순서·문구의 422다. 조회 전용(user)은 403, 비로그인은 401(401이 먼저).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.deals import (
    OWNER_NOT_SALES,
    OWNER_RESIGNED,
    customer_draft,
    deal_body,
    given_deal,
    given_label_id,
    given_my_user_id,
    partner_draft,
    then_deal_count_is,
    when_register_deal,
    when_register_deal_with_body,
)
from tests.functional.steps.session import when_log_out
from tests.functional.steps.users import id_of, when_delete_user

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

AMOUNT = "매출금액은 1원 이상의 정수로 입력하세요."
USERS = "Users는 0 이상의 정수로 입력하세요."


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"name": "  "}, "Deal Name을 입력하세요."),
        ({"name": "가" * 201}, "Deal Name은 200자 이내로 입력하세요."),
        ({"revenue_amount": 0}, AMOUNT),
        ({"revenue_amount": 2**53}, AMOUNT),
        ({"revenue_date": None}, "Expected Close를 입력하세요."),
        ({"users": -1}, USERS),
        ({"users": 2_147_483_648}, USERS),
        ({"status_key": ""}, "Status를 선택하세요."),
        ({"forecast_key": "no_such"}, "Forecast를 선택하세요."),
        (
            {"status_key": "contract_completed", "forecast_key": "pipeline"},
            "Status와 Forecast의 동기화가 맞지 않습니다.",
        ),
        ({"procurement": "가" * 501}, "구매절차는 500자 이내로 입력하세요."),
        ({"customer": customer_draft(company="")}, "고객 회사명을 입력하세요."),
        ({"customer": customer_draft(name="")}, "고객 담당자명을 입력하세요."),
        (
            {"partner": partner_draft(company="", name="")},
            "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.",
        ),
        ({"customer": customer_draft(email="not-an-email")}, "이메일 형식이 올바르지 않습니다."),
        ({"customer": customer_draft(company="네 오인")}, "공백은 입력할 수 없습니다."),
    ],
)
async def test_invalid_input_is_a_422_with_the_screen_message_and_stores_nothing(
    api: Api, overrides: dict[str, object], message: str
) -> None:
    """Scenario: 입력 오류는 화면과 같은 문구의 422(invalid-value)이고 아무것도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, **overrides)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == message
    await then_deal_count_is(api, 0)


async def test_the_earliest_rule_wins_when_several_inputs_are_wrong(api: Api) -> None:
    """Scenario: 이름과 금액이 모두 틀리면 이름 문구가 먼저 나온다(목업 검증 순서)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, name="", revenue_amount=0, users=-1)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == "Deal Name을 입력하세요."


@pytest.mark.parametrize(
    "overrides",
    [
        {"revenue_amount": "많이"},
        {"revenue_date": "30/06/2026"},
        {"owner_user_id": "x"},
        {"extra": 1},
        {"users": None},
        {"users": "10"},
    ],
)
async def test_a_wrongly_typed_body_is_a_request_validation_error(
    api: Api, overrides: dict[str, object]
) -> None:
    """Scenario: 형식이 틀린 본문은 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, **overrides)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_a_body_without_users_is_a_request_validation_error(api: Api) -> None:
    """Scenario: users 키가 없는 등록 본문은 422(request-validation)이고 Deal은 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    body = await deal_body(api)
    del body["users"]
    # When
    response = await when_register_deal_with_body(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_deal_count_is(api, 0)


async def test_a_label_of_another_category_is_rejected(api: Api) -> None:
    """Scenario: 다른 구분의 Label id를 보내면 422이고 Deal은 만들어지지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    need = await given_label_id(api, category="need", name="모름")
    # When
    response = await when_register_deal(
        api, bant={"budget": need, "authority": None, "need": None, "timeline": None}
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == "BANT Label이 올바르지 않습니다."
    await then_deal_count_is(api, 0)


async def test_an_admin_user_cannot_be_the_owner(api: Api) -> None:
    """Scenario: admin을 Owner로 지정하면 422이다(Owner는 재직 영업 담당자)."""
    # Given
    admin_id = await given_user_registered(api, login_id="boss", role="admin")
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, owner_user_id=admin_id)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == OWNER_NOT_SALES


async def test_a_resigned_sales_user_cannot_be_the_owner(api: Api) -> None:
    """Scenario: 퇴사한 사용자를 Owner로 지정하면 전용 문구의 422이다."""
    # Given
    await given_logged_in_as(api, role="sales", login_id="park")
    park_id = await given_my_user_id(api)
    await given_deal(api)  # park가 Owner인 Deal이 있어 삭제하면 퇴사 처리가 된다
    await given_logged_in_as(api, role="admin")
    await when_delete_user(api, await id_of(api, "park"))
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, owner_user_id=park_id)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == OWNER_RESIGNED


async def test_a_read_only_user_cannot_register(api: Api) -> None:
    """Scenario: 조회 전용(user)은 등록할 수 없다(403)."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_register_deal(api)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")


async def test_an_anonymous_visitor_cannot_register(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401이 먼저다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await when_log_out(api)
    # When
    response = await api.post("/api/v1/deals", json={})
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
