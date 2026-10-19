"""Feature: 모든 사용자는 Vendor 목록을 보고, Vendor·Solution 변경(생성 포함)은 admin만 한다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import RoleName, given_logged_in_as, given_logged_out
from tests.functional.steps.common import (
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.vendors import (
    ADMIN_DENIED,
    WRITE_OPERATIONS,
    given_vendor,
    then_vendors_are,
    when_create_vendor,
    when_list_vendors,
    when_write,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

VENDOR_FIELDS = {"id", "name", "usage_count", "solutions", "created_at", "updated_at"}
SOLUTION_FIELDS = {"id", "vendor_id", "name", "usage_count", "created_at", "updated_at"}


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_sees_the_vendor_list(api: Api, role: RoleName) -> None:
    """Scenario: admin·sales·user 모두 Vendor 목록을 볼 수 있다."""
    # Given
    await given_vendor(api, "SAP", ["S/4HANA"])
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_vendors(api)
    # Then
    then_status_is(response, 200)
    assert [v["name"] for v in response.json()] == ["SAP"]


@pytest.mark.parametrize("operation", WRITE_OPERATIONS)
@pytest.mark.parametrize("role", ["sales", "user"])
async def test_only_admin_can_change_vendors(api: Api, role: RoleName, operation: str) -> None:
    """Scenario: sales·user는 Vendor·Solution을 만들거나 바꾸거나 지울 수 없다(403)."""
    # Given
    sap = await given_vendor(api, "SAP", ["Cloud"])
    await given_logged_in_as(api, role=role)
    # When
    response = await when_write(
        api, operation, vendor_id=sap.id, solution_id=sap.solutions["Cloud"]
    )
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_vendors_are(api, [("SAP", ["Cloud"])])


async def test_sales_is_told_that_an_administrator_is_required(api: Api) -> None:
    """Scenario: sales가 Vendor를 만들면 관리자 권한이 필요하다는 안내가 나간다."""
    # Given
    await given_vendor(api, "SAP")
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_vendor(api, name="X")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == ADMIN_DENIED


async def test_anonymous_cannot_list_vendors(api: Api) -> None:
    """Scenario: 로그인하지 않으면 Vendor 목록은 401이다."""
    # Given
    await given_vendor(api, "SAP")
    await given_logged_out(api)
    # When
    response = await when_list_vendors(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


@pytest.mark.parametrize("operation", WRITE_OPERATIONS)
async def test_anonymous_cannot_change_vendors(api: Api, operation: str) -> None:
    """Scenario: 로그인하지 않으면 Vendor·Solution 변경은 401이다."""
    # Given
    sap = await given_vendor(api, "SAP", ["Cloud"])
    await given_logged_out(api)
    # When
    response = await when_write(
        api, operation, vendor_id=sap.id, solution_id=sap.solutions["Cloud"]
    )
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
