"""Feature: 영업은 Deal의 Solution을 Vendor와 무관한 자유 텍스트로 직접 입력한다.

필수 입력(누락·null은 422 request-validation, 공백만은 422 invalid-value), 앞뒤 공백 제거,
최대 200자, NUL 거부, 대소문자는 입력 그대로다.
수정에서는 보내면 비울 수 없고 생략하면 유지된다.
Vendor를 바꾸거나 비워도 Solution 텍스트는 그대로이고, 변경은 History에 텍스트로 남는다.
폐지된 `solution_id` 필드는 거절된다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    given_deal,
    then_deal_keeps,
    then_history_is,
    when_get_deal,
    when_register_deal,
    when_register_deal_omitting,
    when_update_deal,
    when_update_deal_with_body,
)
from tests.functional.steps.vendors import (
    SOLUTION_LONG,
    SOLUTION_REQUIRED,
    UNKNOWN_VENDOR,
    given_vendor,
)
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_sales_registers_deal_with_solution_text_without_vendor(api: Api) -> None:
    """Scenario: Vendor 없이 앞뒤 공백이 있는 Solution 텍스트로 등록하면 공백이 지워져 저장된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution="  ITDR  ")
    # Then
    then_status_is(response, 201)
    assert response.json()["solution"] == "ITDR"
    assert response.json()["vendor"] is None
    await then_deal_keeps(api, response.json()["code"], solution="ITDR", vendor=None)


async def test_omitted_solution_is_rejected(api: Api) -> None:
    """Scenario: solution을 아예 보내지 않은 등록은 422(request-validation)이고 Deal이 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal_omitting(api, "solution")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    assert (await api.get("/api/v1/deals")).json()["total"] == 0


async def test_null_solution_is_rejected(api: Api) -> None:
    """Scenario: solution을 null로 보낸 등록은 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution=None)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("blank", ["", "   "])
async def test_blank_solution_is_rejected(api: Api, blank: str) -> None:
    """Scenario: 비었거나 공백뿐인 solution은 422(invalid-value)와 입력 안내 문구다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution=blank)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SOLUTION_REQUIRED


async def test_solution_keeps_letter_case_and_unicode(api: Api) -> None:
    """Scenario: 대소문자와 한글이 섞인 Solution은 입력 그대로 저장된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution="itDR 통합 보안")
    # Then
    then_status_is(response, 201)
    await then_deal_keeps(api, response.json()["code"], solution="itDR 통합 보안")


async def test_solution_of_200_characters_is_accepted(api: Api) -> None:
    """Scenario: 정확히 200자인 Solution은 통과한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution="가" * 200)
    # Then
    then_status_is(response, 201)
    assert response.json()["solution"] == "가" * 200


async def test_too_long_solution_is_rejected(api: Api) -> None:
    """Scenario: 201자 Solution은 422(invalid-value)와 안내 문구이고 Deal이 만들어지지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution="가" * 201)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SOLUTION_LONG


async def test_solution_with_a_nul_character_is_rejected(api: Api) -> None:
    """Scenario: NUL 문자가 있는 Solution은 422(invalid-value)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution="IT\u0000DR")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


async def test_unknown_vendor_is_reported_before_a_too_long_solution(api: Api) -> None:
    """Scenario: 없는 Vendor와 201자 Solution을 함께 보내면 Vendor 문구가 먼저 나간다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor_id=MISSING_ID, solution="a" * 201)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == UNKNOWN_VENDOR


async def test_non_string_solution_is_rejected(api: Api) -> None:
    """Scenario: 숫자 Solution은 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution=12)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_old_solution_id_field_is_rejected(api: Api) -> None:
    """Scenario: 구 필드 solution_id를 포함한 등록은 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution_id=1)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_old_solution_id_field_is_rejected_on_update(api: Api) -> None:
    """Scenario: 구 필드 solution_id를 포함한 수정은 422(request-validation)이고 Deal은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, solution="ITDR")
    # When
    response = await when_update_deal_with_body(api, deal["code"], {"solution_id": 1})
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_deal_keeps(api, deal["code"], solution="ITDR")


async def test_patch_replaces_the_solution_text_and_records_history(api: Api) -> None:
    """Scenario: solution을 바꾸면 새 값(공백 제거)이 저장되고 History에 이전·이후가 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, solution="MFA")
    # When
    response = await when_update_deal(api, deal["code"], solution="  ITDR ")
    # Then
    then_status_is(response, 200)
    assert response.json()["solution"] == "ITDR"
    await then_history_is(api, deal["code"], [("other", "Solution", "MFA", "ITDR")])


@pytest.mark.parametrize("sent", [None, "", "   "])
async def test_solution_cannot_be_cleared(api: Api, sent: str | None) -> None:
    """Scenario: solution을 null·빈 문자열·공백으로 보낸 수정은 422이고 값이 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, solution="ITDR")
    # When
    response = await when_update_deal(api, deal["code"], solution=sent)
    # Then
    assert response.status_code == 422, response.text
    await then_deal_keeps(api, deal["code"], solution="ITDR")
    await then_history_is(api, deal["code"], [])


async def test_too_long_solution_on_update_is_rejected(api: Api) -> None:
    """Scenario: 201자 solution으로 수정하면 422(invalid-value)이고 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, solution="ITDR")
    # When
    response = await when_update_deal(api, deal["code"], solution="가" * 201)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SOLUTION_LONG
    await then_deal_keeps(api, deal["code"], solution="ITDR")


async def test_case_only_change_is_recorded(api: Api) -> None:
    """Scenario: 대소문자만 바꿔도 History가 남고 앞뒤 공백만 다른 값은 남지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, solution="itdr")
    await when_update_deal(api, deal["code"], solution=" itdr ")
    # When
    response = await when_update_deal(api, deal["code"], solution="ITDR")
    # Then
    then_status_is(response, 200)
    await then_history_is(api, deal["code"], [("other", "Solution", "itdr", "ITDR")])


async def test_patch_without_solution_keeps_the_text(api: Api) -> None:
    """Scenario: solution을 보내지 않은 수정은 기존 텍스트를 유지한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, solution="ITDR")
    # When
    response = await when_update_deal(api, deal["code"], name="다른 이름")
    # Then
    then_status_is(response, 200)
    await then_deal_keeps(api, deal["code"], name="다른 이름", solution="ITDR")


async def test_changing_vendor_keeps_solution_text(api: Api) -> None:
    """Scenario: Vendor만 바꾸면 Solution은 그대로이고 History에 Vendor만 1건 남는다."""
    # Given
    sap = await given_vendor(api, "SAP")
    oracle = await given_vendor(api, "Oracle")
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id, solution="ITDR")
    # When
    response = await when_update_deal(api, deal["code"], vendor_id=oracle.id)
    # Then
    then_status_is(response, 200)
    assert response.json()["solution"] == "ITDR"
    await then_history_is(api, deal["code"], [("other", "Vendor", "SAP", "Oracle")])


async def test_solution_can_be_entered_on_a_deal_without_vendor_later(api: Api) -> None:
    """Scenario: Vendor가 없는 Deal에도 Solution 텍스트를 나중에 입력할 수 있다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(api, deal["code"], solution="ITDR")
    # Then
    then_status_is(response, 200)
    got = await when_get_deal(api, deal["code"])
    assert (got.json()["vendor"], got.json()["solution"]) == (None, "ITDR")
