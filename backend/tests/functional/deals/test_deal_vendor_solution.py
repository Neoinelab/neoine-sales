"""Feature: 영업은 등록된 Vendor를 Deal에 고르고, Solution 텍스트는 Vendor와 독립이다.

Deal의 Vendor는 등록 목록(`/vendors`)에서 고른 id로만 저장된다. 이름 변경은 모든 Deal에 반영되고,
History는 변경 당시 이름으로 남는다. Solution 자유 텍스트 규칙은 `test_deal_solution_text.py`.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    given_deal,
    list_codes,
    then_deal_keeps,
    then_history_is,
    when_get_deal,
    when_list_deals,
    when_register_deal,
    when_update_deal,
)
from tests.functional.steps.vendors import (
    UNKNOWN_VENDOR,
    VendorRef,
    given_vendor,
    when_rename_vendor,
)
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


def _ref(vendor_id: int, name: str) -> dict[str, int | str]:
    return {"id": vendor_id, "name": name}


async def _sap_and_oracle(api: Api) -> tuple[VendorRef, VendorRef]:
    sap = await given_vendor(api, "SAP")
    oracle = await given_vendor(api, "Oracle")
    return sap, oracle


async def test_deal_is_registered_with_a_vendor(api: Api) -> None:
    """Scenario: Vendor id로 등록하면 응답의 vendor가 {id, name}이고 solution은 입력한 텍스트다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor_id=sap.id, solution="ITDR")
    # Then
    then_status_is(response, 201)
    body = response.json()
    assert body["vendor"] == _ref(sap.id, "SAP")
    assert body["solution"] == "ITDR"
    await then_deal_keeps(api, body["code"], vendor=_ref(sap.id, "SAP"), solution="ITDR")


async def test_a_deal_may_have_no_vendor(api: Api) -> None:
    """Scenario: Vendor를 고르지 않고 등록해도 된다(vendor는 null)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api)
    # Then
    then_status_is(response, 201)
    assert response.json()["vendor"] is None


async def test_list_rows_carry_the_vendor_name_and_the_solution_text(api: Api) -> None:
    """Scenario: 목록의 각 행은 vendor를 {id, name} 또는 null로, solution을 문자열로 보인다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    full = await given_deal(api, vendor_id=sap.id, solution="BW")
    empty = await given_deal(api, solution="MFA")
    # When
    response = await when_list_deals(api)
    # Then
    rows = {row["code"]: row for row in response.json()["items"]}
    assert rows[full["code"]]["vendor"] == _ref(sap.id, "SAP")
    assert rows[full["code"]]["solution"] == "BW"
    assert (rows[empty["code"]]["vendor"], rows[empty["code"]]["solution"]) == (None, "MFA")


async def test_unknown_vendor_is_rejected(api: Api) -> None:
    """Scenario: 목록에 없는 Vendor id를 보내면 422이고 다시 선택하라는 문구가 나간다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor_id=MISSING_ID)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == UNKNOWN_VENDOR
    assert (await when_list_deals(api)).json()["total"] == 0


async def test_the_old_text_vendor_field_is_rejected(api: Api) -> None:
    """Scenario: 구 필드 vendor(문자열)는 모르는 필드라 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor="SAP")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_unknown_vendor_on_update_is_rejected_and_the_deal_is_unchanged(api: Api) -> None:
    """Scenario: 수정에서 없는 Vendor id를 보내면 422이고 Deal은 그대로다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id)
    # When
    response = await when_update_deal(api, deal["code"], vendor_id=MISSING_ID)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == UNKNOWN_VENDOR
    await then_deal_keeps(api, deal["code"], vendor=_ref(sap.id, "SAP"))


async def test_choosing_a_vendor_for_the_first_time_records_not_selected_as_before(
    api: Api,
) -> None:
    """Scenario: 처음 Vendor를 고르면 History의 이전 값은 '선택 안 함'이다(Solution 항목 없음)."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(api, deal["code"], vendor_id=sap.id)
    # Then
    then_status_is(response, 200)
    await then_history_is(api, deal["code"], [("other", "Vendor", "선택 안 함", "SAP")])


async def test_clearing_the_vendor_records_history_and_keeps_the_solution(api: Api) -> None:
    """Scenario: vendor_id=null로 비우면 Vendor 항목만 남고 Solution 텍스트는 그대로다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id, solution="ITDR")
    # When
    response = await when_update_deal(api, deal["code"], vendor_id=None)
    # Then
    then_status_is(response, 200)
    assert response.json()["vendor"] is None
    assert response.json()["solution"] == "ITDR"
    await then_history_is(api, deal["code"], [("other", "Vendor", "SAP", "선택 안 함")])


async def test_sending_the_same_vendor_again_leaves_no_history(api: Api) -> None:
    """Scenario: 같은 Vendor를 다시 보내면 History가 늘지 않는다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id)
    # When
    response = await when_update_deal(api, deal["code"], vendor_id=sap.id)
    # Then
    then_status_is(response, 200)
    await then_history_is(api, deal["code"], [])


async def test_renamed_vendor_appears_on_every_deal_and_history_keeps_the_old_name(
    api: Api,
) -> None:
    """Scenario: Vendor 이름을 바꾸면 모든 Deal에 새 이름이 나오고 History는 그대로다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    await when_update_deal(api, first["code"], vendor_id=sap.id)
    second = await given_deal(api, vendor_id=sap.id)
    await given_logged_in_as(api, role="admin")
    # When
    renamed = await when_rename_vendor(api, vendor_id=sap.id, name="SAP Korea")
    # Then
    then_status_is(renamed, 200)
    assert renamed.json()["usage_count"] == 2
    listing = await when_list_deals(api)
    assert {row["vendor"]["name"] for row in listing.json()["items"]} == {"SAP Korea"}
    assert (await when_get_deal(api, first["code"])).json()["vendor"]["name"] == "SAP Korea"
    assert (await when_get_deal(api, second["code"])).json()["vendor"]["name"] == "SAP Korea"
    await then_history_is(api, first["code"], [("other", "Vendor", "선택 안 함", "SAP")])


async def test_a_deal_is_found_by_the_vendor_filter_after_it_is_chosen(api: Api) -> None:
    """Scenario: Vendor를 고른 뒤 vendor_id 필터로 그 Deal이 목록에서 찾아진다."""
    # Given
    sap, oracle = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_deal(api, vendor_id=oracle.id)
    await when_update_deal(api, deal["code"], vendor_id=sap.id)
    # When
    response = await when_list_deals(api, vendor_id=sap.id)
    # Then
    assert list_codes(response) == [deal["code"]]
