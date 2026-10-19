"""Feature: 영업은 등록된 Vendor와 그 Vendor의 Solution만 Deal에 고른다.

Deal의 Vendor·Solution은 등록 목록(`/vendors`)에서 고른 id로만 저장된다. Solution은 선택한 Vendor의
것이어야 하고, Vendor를 바꾸면 화면이 Solution을 `null`로 함께 보내 비운다. 이름 변경은 모든 Deal에
반영되고, History는 변경 당시 이름으로 남는다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

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
    SOLUTION_MISMATCH,
    SOLUTION_NEEDS_VENDOR,
    UNKNOWN_VENDOR,
    VendorRef,
    given_vendor,
    when_rename_solution,
    when_rename_vendor,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


def _ref(vendor_id: str, name: str) -> dict[str, str]:
    return {"id": vendor_id, "name": name}


async def _sap_and_oracle(api: Api) -> tuple[VendorRef, VendorRef]:
    sap = await given_vendor(api, "SAP", ["S/4HANA", "BW"])
    oracle = await given_vendor(api, "Oracle", ["EBS"])
    return sap, oracle


async def test_deal_is_registered_with_a_vendor_and_its_solution(api: Api) -> None:
    """Scenario: Vendor와 그 Solution의 id로 등록하면 응답의 vendor·solution이 {id, name}이다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"])
    # Then
    then_status_is(response, 201)
    body = response.json()
    assert body["vendor"] == _ref(sap.id, "SAP")
    assert body["solution"] == _ref(sap.solutions["S/4HANA"], "S/4HANA")
    await then_deal_keeps(api, body["code"], vendor=_ref(sap.id, "SAP"), solution=body["solution"])


async def test_a_deal_may_have_a_vendor_without_a_solution(api: Api) -> None:
    """Scenario: Solution 없이 Vendor만 골라 등록해도 된다(solution은 null)."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor_id=sap.id)
    # Then
    then_status_is(response, 201)
    assert response.json()["vendor"] == _ref(sap.id, "SAP")
    assert response.json()["solution"] is None


async def test_a_deal_may_have_neither_vendor_nor_solution(api: Api) -> None:
    """Scenario: Vendor도 Solution도 고르지 않고 등록해도 된다(둘 다 null)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api)
    # Then
    then_status_is(response, 201)
    assert (response.json()["vendor"], response.json()["solution"]) == (None, None)


async def test_list_rows_carry_the_vendor_and_solution_names(api: Api) -> None:
    """Scenario: 목록의 각 행도 vendor·solution을 {id, name} 또는 null로 보인다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    full = await given_deal(api, vendor_id=sap.id, solution_id=sap.solutions["BW"])
    empty = await given_deal(api)
    # When
    response = await when_list_deals(api)
    # Then
    rows = {row["code"]: row for row in response.json()["items"]}
    assert rows[full["code"]]["vendor"] == _ref(sap.id, "SAP")
    assert rows[full["code"]]["solution"] == _ref(sap.solutions["BW"], "BW")
    assert (rows[empty["code"]]["vendor"], rows[empty["code"]]["solution"]) == (None, None)


async def test_solution_of_another_vendor_is_rejected(api: Api) -> None:
    """Scenario: 다른 Vendor의 Solution을 고르면 422(invalid-value)이고 Deal이 만들어지지 않는다."""
    # Given
    sap, oracle = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor_id=sap.id, solution_id=oracle.solutions["EBS"])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SOLUTION_MISMATCH
    assert (await when_list_deals(api)).json()["total"] == 0


async def test_solution_without_vendor_is_rejected(api: Api) -> None:
    """Scenario: Vendor 없이 Solution만 보내면 422이고 먼저 Vendor를 고르라는 문구가 나간다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, solution_id=sap.solutions["BW"])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SOLUTION_NEEDS_VENDOR


async def test_unknown_vendor_is_rejected(api: Api) -> None:
    """Scenario: 목록에 없는 Vendor id를 보내면 422이고 다시 선택하라는 문구가 나간다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, vendor_id=str(uuid4()))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == UNKNOWN_VENDOR


@pytest.mark.parametrize("field", ["vendor", "solution"])
async def test_the_old_text_fields_are_rejected(api: Api, field: str) -> None:
    """Scenario: 구 필드 vendor·solution(문자열)은 모르는 필드라 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, **{field: "SAP"})
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_changing_vendor_alone_while_the_solution_belongs_to_the_old_one_is_rejected(
    api: Api,
) -> None:
    """Scenario: Vendor만 바꾸고 Solution을 비우지 않으면 422이고 Deal은 그대로다."""
    # Given
    sap, oracle = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"])
    # When
    response = await when_update_deal(api, deal["code"], vendor_id=oracle.id)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SOLUTION_MISMATCH
    await then_deal_keeps(api, deal["code"], vendor=deal["vendor"], solution=deal["solution"])


async def test_changing_vendor_clears_solution_and_records_history(api: Api) -> None:
    """Scenario: vendor_id와 solution_id=null을 함께 보내면 바뀌고 History가 두 건 남는다."""
    # Given
    sap, oracle = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"])
    # When
    response = await when_update_deal(api, deal["code"], vendor_id=oracle.id, solution_id=None)
    # Then
    then_status_is(response, 200)
    assert response.json()["vendor"] == _ref(oracle.id, "Oracle")
    assert response.json()["solution"] is None
    await then_history_is(
        api,
        deal["code"],
        [
            ("other", "Vendor", "SAP", "Oracle"),
            ("other", "Solution", "S/4HANA", "선택 안 함"),
        ],
    )


async def test_choosing_a_vendor_for_the_first_time_records_not_selected_as_before(
    api: Api,
) -> None:
    """Scenario: 처음 Vendor를 고르면 History의 이전 값은 '선택 안 함'이다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(
        api, deal["code"], vendor_id=sap.id, solution_id=sap.solutions["BW"]
    )
    # Then
    then_status_is(response, 200)
    await then_history_is(
        api,
        deal["code"],
        [
            ("other", "Vendor", "선택 안 함", "SAP"),
            ("other", "Solution", "선택 안 함", "BW"),
        ],
    )


async def test_sending_the_same_choice_again_leaves_no_history(api: Api) -> None:
    """Scenario: 같은 Vendor·Solution을 다시 보내면 History가 늘지 않는다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id, solution_id=sap.solutions["BW"])
    # When
    response = await when_update_deal(
        api, deal["code"], vendor_id=sap.id, solution_id=sap.solutions["BW"]
    )
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


async def test_renamed_solution_appears_on_the_deals_that_use_it(api: Api) -> None:
    """Scenario: Solution 이름을 바꾸면 그 Solution을 쓰는 Deal의 solution.name이 바뀐다."""
    # Given
    sap, _ = await _sap_and_oracle(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id, solution_id=sap.solutions["BW"])
    await given_logged_in_as(api, role="admin")
    # When
    renamed = await when_rename_solution(
        api, vendor_id=sap.id, solution_id=sap.solutions["BW"], name="BW/4HANA"
    )
    # Then
    then_status_is(renamed, 200)
    assert renamed.json()["usage_count"] == 1
    assert (await when_get_deal(api, deal["code"])).json()["solution"] == _ref(
        sap.solutions["BW"], "BW/4HANA"
    )


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
