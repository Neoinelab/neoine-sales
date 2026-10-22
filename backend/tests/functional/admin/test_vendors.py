"""Feature: admin은 Vendor를 등록·이름 변경하고, 목록은 이름순으로 나온다(Solution 관리는 없다).

Solution은 Deal의 자유 텍스트다. 이름 규칙·중복은 `test_vendor_names.py`, 삭제는
`test_vendor_deletion.py`, 권한은 `test_vendor_permissions.py`, Deal 연동은
`deals/test_deal_solution_text.py`.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import (
    then_body_includes,
    then_status_is,
)
from tests.functional.steps.vendors import (
    REMOVED_SOLUTION_CALLS,
    VENDOR_FIELDS,
    VENDORS,
    given_vendor,
    then_location_points_to,
    then_vendors_are,
    when_call_removed_solution_api,
    when_create_vendor,
    when_list_vendors,
    when_rename_vendor,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_creates_a_vendor(api: Api) -> None:
    """Scenario: admin이 Vendor를 만들면 201, Location, 사용 0건 본문(solutions 없음)이 나간다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_vendor(api, name="  SAP  ")
    # Then
    then_status_is(response, 201)
    assert set(response.json()) == VENDOR_FIELDS
    then_body_includes(response, name="SAP", usage_count=0)
    then_location_points_to(response, f"{VENDORS}/{response.json()['id']}")
    await then_vendors_are(api, ["SAP"])


async def test_admin_renames_a_vendor(api: Api) -> None:
    """Scenario: admin이 Vendor 이름을 바꾸면 200과 바뀐 Vendor(사용 수 포함)가 나간다."""
    # Given
    sap = await given_vendor(api, "SAP")
    # When
    response = await when_rename_vendor(api, vendor_id=sap.id, name="SAP Korea")
    # Then
    then_status_is(response, 200)
    assert set(response.json()) == VENDOR_FIELDS
    then_body_includes(response, name="SAP Korea", usage_count=0)
    await then_vendors_are(api, ["SAP Korea"])


async def test_admin_manages_vendor_without_solutions(api: Api) -> None:
    """Scenario: Vendor를 만들고 이름을 바꾼 뒤 목록을 보면 항목에 solutions가 없고 이름순이다."""
    # Given
    await given_vendor(api, "zeta")
    await given_vendor(api, "Oracle")
    sap = await given_vendor(api, "sap")
    await when_rename_vendor(api, vendor_id=sap.id, name="Sap Korea")
    # When
    response = await when_list_vendors(api)
    # Then
    then_status_is(response, 200)
    assert [v["name"] for v in response.json()] == ["Oracle", "Sap Korea", "zeta"]
    assert all(set(v) == VENDOR_FIELDS for v in response.json())


@pytest.mark.parametrize("call", REMOVED_SOLUTION_CALLS)
async def test_solution_management_api_is_gone(api: Api, call: str) -> None:
    """Scenario: admin이 폐지된 Solution 관리 경로를 호출하면 모두 404다."""
    # Given
    sap = await given_vendor(api, "SAP")
    # When
    response = await when_call_removed_solution_api(api, call, vendor_id=sap.id)
    # Then
    assert response.status_code == 404, response.text
    await then_vendors_are(api, ["SAP"])
