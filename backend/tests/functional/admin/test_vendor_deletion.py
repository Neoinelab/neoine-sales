"""Feature: 쓰는 Deal이 있는 Vendor·Solution은 못 지우고, 안 쓰는 Vendor는 소속과 함께 지운다."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import (
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.deals import given_deal
from tests.functional.steps.vendors import (
    VendorRef,
    given_vendor,
    in_use_solution,
    in_use_vendor,
    then_usage_is,
    then_vendors_are,
    when_delete_solution,
    when_delete_vendor,
    when_write,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

VENDOR_FIELDS = {"id", "name", "usage_count", "solutions", "created_at", "updated_at"}
SOLUTION_FIELDS = {"id", "vendor_id", "name", "usage_count", "created_at", "updated_at"}


async def test_deleting_a_solution_under_another_vendors_path_is_not_found(api: Api) -> None:
    """Scenario: 다른 Vendor 경로로 Solution을 지우면 404이고 Solution은 남는다."""
    # Given
    sap = await given_vendor(api, "SAP", ["Cloud"])
    oracle = await given_vendor(api, "Oracle")
    # When
    response = await when_delete_solution(
        api, vendor_id=oracle.id, solution_id=sap.solutions["Cloud"]
    )
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    await then_vendors_are(api, [("Oracle", []), ("SAP", ["Cloud"])])


@pytest.mark.parametrize("operation", ["rename_vendor", "delete_vendor", "create_solution"])
async def test_unknown_vendor_ids_are_not_found(api: Api, operation: str) -> None:
    """Scenario: 없는 Vendor id를 대상으로 한 이름 변경·삭제·Solution 추가는 404다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_write(api, operation, vendor_id=str(uuid4()), solution_id=str(uuid4()))
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def _vendor_used_by_a_deal(api: Api) -> VendorRef:
    sap = await given_vendor(api, "SAP", ["S/4HANA", "BW"])
    await given_logged_in_as(api, role="sales")
    await given_deal(api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"])
    await given_logged_in_as(api, role="admin")
    return sap


async def test_a_solution_used_by_a_deal_cannot_be_deleted(api: Api) -> None:
    """Scenario: Deal이 쓰는 Solution은 삭제할 수 없고(409, 건수) 목록에 그대로 있다."""
    # Given
    sap = await _vendor_used_by_a_deal(api)
    # When
    response = await when_delete_solution(
        api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"]
    )
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == in_use_solution(1)
    await then_vendors_are(api, [("SAP", ["BW", "S/4HANA"])])
    await then_usage_is(api, vendor="SAP", solution="S/4HANA", count=1)
    await then_usage_is(api, vendor="SAP", solution="BW", count=0)


async def test_a_vendor_whose_solution_is_used_by_a_deal_cannot_be_deleted(api: Api) -> None:
    """Scenario: Deal이 Vendor와 그 Solution을 쓰면 Vendor 삭제는 409이고 둘 다 남는다."""
    # Given
    sap = await _vendor_used_by_a_deal(api)
    # When
    response = await when_delete_vendor(api, vendor_id=sap.id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == in_use_vendor(1)
    await then_vendors_are(api, [("SAP", ["BW", "S/4HANA"])])
    await then_usage_is(api, vendor="SAP", count=1)


async def test_a_vendor_used_only_as_a_vendor_cannot_be_deleted_either(api: Api) -> None:
    """Scenario: Solution 없이 Vendor만 고른 Deal이 있어도 Vendor는 지울 수 없고 건수가 센다."""
    # Given
    sap = await given_vendor(api, "SAP", ["BW"])
    await given_logged_in_as(api, role="sales")
    await given_deal(api, vendor_id=sap.id)
    await given_deal(api, vendor_id=sap.id)
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_vendor(api, vendor_id=sap.id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == in_use_vendor(2)
    await then_vendors_are(api, [("SAP", ["BW"])])


async def test_unused_solution_is_deleted(api: Api) -> None:
    """Scenario: 쓰는 Deal이 없는 Solution은 204로 삭제되고 나머지는 남는다."""
    # Given
    sap = await given_vendor(api, "SAP", ["S/4HANA", "BW"])
    # When
    response = await when_delete_solution(api, vendor_id=sap.id, solution_id=sap.solutions["BW"])
    # Then
    then_status_is(response, 204)
    await then_vendors_are(api, [("SAP", ["S/4HANA"])])


async def test_unused_vendor_is_deleted_with_its_solutions(api: Api) -> None:
    """Scenario: 쓰는 Deal이 없는 Vendor는 204로 삭제되고 소속 Solution도 함께 사라진다."""
    # Given
    sap = await given_vendor(api, "SAP", ["S/4HANA", "BW"])
    await given_vendor(api, "Oracle", ["EBS"])
    # When
    response = await when_delete_vendor(api, vendor_id=sap.id)
    # Then
    then_status_is(response, 204)
    await then_vendors_are(api, [("Oracle", ["EBS"])])


async def test_deleting_the_last_deal_of_a_vendor_frees_it_for_deletion(api: Api) -> None:
    """Scenario: 그 Vendor를 쓰던 Deal이 삭제되면 Vendor를 지울 수 있다."""
    # Given
    sap = await given_vendor(api, "SAP")
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id)
    await api.delete(f"/api/v1/deals/{deal['code']}?confirm_code={deal['code']}")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_vendor(api, vendor_id=sap.id)
    # Then
    then_status_is(response, 204)
