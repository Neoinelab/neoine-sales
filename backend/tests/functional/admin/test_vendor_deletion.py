"""Feature: 쓰는 Deal이 있는 Vendor는 못 지우고, 안 쓰는 Vendor는 지운다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import (
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.deals import given_deal
from tests.functional.steps.vendors import (
    given_vendor,
    in_use_vendor,
    then_usage_is,
    then_vendors_are,
    when_delete_vendor,
    when_write,
)
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("operation", ["rename_vendor", "delete_vendor"])
async def test_unknown_vendor_ids_are_not_found(api: Api, operation: str) -> None:
    """Scenario: 없는 Vendor id를 대상으로 한 이름 변경·삭제는 404다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_write(api, operation, vendor_id=MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_vendor_used_by_deal_cannot_be_deleted(api: Api) -> None:
    """Scenario: Vendor를 쓰는 Deal이 2건 있으면 삭제는 409(건수)이고 Vendor가 남는다."""
    # Given
    sap = await given_vendor(api, "SAP")
    await given_logged_in_as(api, role="sales")
    await given_deal(api, vendor_id=sap.id)
    await given_deal(api, vendor_id=sap.id, solution="ITDR")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_vendor(api, vendor_id=sap.id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == in_use_vendor(2)
    await then_vendors_are(api, ["SAP"])
    await then_usage_is(api, vendor="SAP", count=2)


async def test_a_deal_with_only_a_solution_text_does_not_hold_a_vendor(api: Api) -> None:
    """Scenario: Solution 텍스트만 있고 Vendor가 없는 Deal은 다른 Vendor의 삭제를 막지 않는다."""
    # Given
    sap = await given_vendor(api, "SAP")
    await given_logged_in_as(api, role="sales")
    await given_deal(api, solution="SAP")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_vendor(api, vendor_id=sap.id)
    # Then
    then_status_is(response, 204)


async def test_unused_vendor_is_deleted(api: Api) -> None:
    """Scenario: 쓰는 Deal이 없는 Vendor는 204로 삭제되고 목록에서 사라진다."""
    # Given
    sap = await given_vendor(api, "SAP")
    await given_vendor(api, "Oracle")
    # When
    response = await when_delete_vendor(api, vendor_id=sap.id)
    # Then
    then_status_is(response, 204)
    await then_vendors_are(api, ["Oracle"])


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
