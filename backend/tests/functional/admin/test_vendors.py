"""Feature: admin은 Vendor와 그 Solution을 등록·이름 변경하고, 목록은 이름순으로 나온다.

Solution은 Vendor에 종속(1:N)이다. 이름 규칙·중복은 `test_vendor_names.py`, 삭제는
`test_vendor_deletion.py`, 권한은 `test_vendor_permissions.py`, Deal 연동은
`deals/test_deal_vendor_solution.py`.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import (
    then_body_includes,
    then_status_is,
)
from tests.functional.steps.vendors import (
    VENDORS,
    given_vendor,
    then_location_points_to,
    then_vendors_are,
    when_create_solution,
    when_create_vendor,
    when_list_vendors,
    when_rename_solution,
    when_rename_vendor,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

VENDOR_FIELDS = {"id", "name", "usage_count", "solutions", "created_at", "updated_at"}
SOLUTION_FIELDS = {"id", "vendor_id", "name", "usage_count", "created_at", "updated_at"}


async def test_admin_creates_a_vendor(api: Api) -> None:
    """Scenario: admin이 Vendor를 만들면 201, Location, 사용 0건·Solution 없음 본문이 나간다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_vendor(api, name="  SAP  ")
    # Then
    then_status_is(response, 201)
    assert set(response.json()) == VENDOR_FIELDS
    then_body_includes(response, name="SAP", usage_count=0, solutions=[])
    then_location_points_to(response, f"{VENDORS}/{response.json()['id']}")
    await then_vendors_are(api, [("SAP", [])])


async def test_admin_creates_a_solution_under_a_vendor(api: Api) -> None:
    """Scenario: admin이 Vendor 아래에 Solution을 만들면 201과 Location이 나가고 목록에 보인다."""
    # Given
    sap = await given_vendor(api, "SAP")
    # When
    response = await when_create_solution(api, vendor_id=sap.id, name="  S/4HANA ")
    # Then
    then_status_is(response, 201)
    assert set(response.json()) == SOLUTION_FIELDS
    then_body_includes(response, name="S/4HANA", vendor_id=sap.id, usage_count=0)
    then_location_points_to(response, f"{VENDORS}/{sap.id}/solutions/{response.json()['id']}")
    await then_vendors_are(api, [("SAP", ["S/4HANA"])])


async def test_admin_renames_a_vendor(api: Api) -> None:
    """Scenario: admin이 Vendor 이름을 바꾸면 200과 바뀐 Vendor(사용 수 포함)가 나간다."""
    # Given
    sap = await given_vendor(api, "SAP", ["S/4HANA"])
    # When
    response = await when_rename_vendor(api, vendor_id=sap.id, name="SAP Korea")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, name="SAP Korea", usage_count=0)
    await then_vendors_are(api, [("SAP Korea", ["S/4HANA"])])


async def test_admin_renames_a_solution(api: Api) -> None:
    """Scenario: admin이 Solution 이름을 바꾸면 200이고 목록에 새 이름이 보인다."""
    # Given
    sap = await given_vendor(api, "SAP", ["S/4HANA"])
    # When
    response = await when_rename_solution(
        api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"], name="S/4HANA Cloud"
    )
    # Then
    then_status_is(response, 200)
    then_body_includes(response, name="S/4HANA Cloud", vendor_id=sap.id)
    await then_vendors_are(api, [("SAP", ["S/4HANA Cloud"])])


async def test_the_list_is_sorted_by_lower_name_for_vendors_and_solutions(api: Api) -> None:
    """Scenario: Vendor와 각 Vendor의 Solution은 대소문자 무시 이름순으로 나온다."""
    # Given
    await given_vendor(api, "zeta")
    await given_vendor(api, "Oracle", ["beta", "Alpha"])
    await given_vendor(api, "sap")
    # When
    response = await when_list_vendors(api)
    # Then
    then_status_is(response, 200)
    await then_vendors_are(api, [("Oracle", ["Alpha", "beta"]), ("sap", []), ("zeta", [])])
