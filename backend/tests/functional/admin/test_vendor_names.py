"""Feature: Vendor·Solution 이름은 공백을 지우고, 길이·NUL을 제한하며, 대소문자 무시로 고유하다.

Vendor 이름은 전역에서, Solution 이름은 같은 Vendor 안에서 고유하다(다른 Vendor와는 같아도 된다).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import (
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.vendors import (
    DUPLICATE_SOLUTION,
    DUPLICATE_VENDOR,
    SOLUTION_BLANK,
    SOLUTION_LONG,
    VENDOR_BLANK,
    VENDOR_LONG,
    given_vendor,
    then_vendors_are,
    when_create_solution,
    when_create_vendor,
    when_rename_solution,
    when_rename_vendor,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

VENDOR_FIELDS = {"id", "name", "usage_count", "solutions", "created_at", "updated_at"}
SOLUTION_FIELDS = {"id", "vendor_id", "name", "usage_count", "created_at", "updated_at"}


async def test_duplicate_vendor_name_ignoring_case_is_rejected(api: Api) -> None:
    """Scenario: 대소문자만 다른 Vendor 이름은 409(already-exists)다."""
    # Given
    await given_vendor(api, "SAP")
    # When
    response = await when_create_vendor(api, name="sap")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_VENDOR
    await then_vendors_are(api, [("SAP", [])])


async def test_duplicate_solution_name_in_the_same_vendor_is_rejected(api: Api) -> None:
    """Scenario: 같은 Vendor 안에 대소문자만 다른 Solution 이름은 409다."""
    # Given
    sap = await given_vendor(api, "SAP", ["Cloud"])
    # When
    response = await when_create_solution(api, vendor_id=sap.id, name="CLOUD")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_SOLUTION


async def test_the_same_solution_name_is_allowed_under_another_vendor(api: Api) -> None:
    """Scenario: 다른 Vendor의 Solution과 같은 이름은 허용된다."""
    # Given
    await given_vendor(api, "SAP", ["Cloud"])
    oracle = await given_vendor(api, "Oracle")
    # When
    response = await when_create_solution(api, vendor_id=oracle.id, name="Cloud")
    # Then
    then_status_is(response, 201)
    await then_vendors_are(api, [("Oracle", ["Cloud"]), ("SAP", ["Cloud"])])


async def test_renaming_a_vendor_to_a_taken_name_is_rejected(api: Api) -> None:
    """Scenario: 다른 Vendor의 이름으로 바꾸면 409이고 이름은 그대로다."""
    # Given
    sap = await given_vendor(api, "SAP")
    await given_vendor(api, "Oracle")
    # When
    response = await when_rename_vendor(api, vendor_id=sap.id, name="ORACLE")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    await then_vendors_are(api, [("Oracle", []), ("SAP", [])])


async def test_renaming_a_vendor_to_its_own_name_in_other_case_is_allowed(api: Api) -> None:
    """Scenario: 자기 이름의 대소문자만 바꾸는 이름 변경은 200이다."""
    # Given
    sap = await given_vendor(api, "Sap")
    # When
    response = await when_rename_vendor(api, vendor_id=sap.id, name="SAP")
    # Then
    then_status_is(response, 200)
    await then_vendors_are(api, [("SAP", [])])


async def test_renaming_a_solution_to_a_sibling_name_is_rejected(api: Api) -> None:
    """Scenario: 같은 Vendor의 다른 Solution 이름으로 바꾸면 409다."""
    # Given
    sap = await given_vendor(api, "SAP", ["Cloud", "ERP"])
    # When
    response = await when_rename_solution(
        api, vendor_id=sap.id, solution_id=sap.solutions["ERP"], name="cloud"
    )
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_SOLUTION


async def test_renaming_a_solution_to_its_own_name_in_other_case_is_allowed(api: Api) -> None:
    """Scenario: Solution도 자기 이름의 대소문자만 바꾸는 변경은 200이다."""
    # Given
    sap = await given_vendor(api, "SAP", ["Cloud"])
    # When
    response = await when_rename_solution(
        api, vendor_id=sap.id, solution_id=sap.solutions["Cloud"], name="CLOUD"
    )
    # Then
    then_status_is(response, 200)
    await then_vendors_are(api, [("SAP", ["CLOUD"])])


@pytest.mark.parametrize(
    ("name", "message"),
    [("   ", VENDOR_BLANK), ("a" * 101, VENDOR_LONG)],
    ids=["blank", "101-chars"],
)
async def test_invalid_vendor_names_are_422(api: Api, name: str, message: str) -> None:
    """Scenario: 공백뿐이거나 101자인 Vendor 이름은 422(invalid-value)와 안내 문구다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_vendor(api, name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == message
    await then_vendors_are(api, [])


@pytest.mark.parametrize(
    ("name", "message"),
    [("   ", SOLUTION_BLANK), ("a" * 201, SOLUTION_LONG)],
    ids=["blank", "201-chars"],
)
async def test_invalid_solution_names_are_422(api: Api, name: str, message: str) -> None:
    """Scenario: 공백뿐이거나 201자인 Solution 이름은 422(invalid-value)와 안내 문구다."""
    # Given
    sap = await given_vendor(api, "SAP")
    # When
    response = await when_create_solution(api, vendor_id=sap.id, name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == message


async def test_the_longest_vendor_and_solution_names_are_accepted(api: Api) -> None:
    """Scenario: 100자 Vendor 이름과 200자 Solution 이름은 통과한다."""
    # Given
    vendor = await given_vendor(api, "a" * 100)
    # When
    response = await when_create_solution(api, vendor_id=vendor.id, name="b" * 200)
    # Then
    then_status_is(response, 201)


async def test_a_nul_character_in_a_vendor_name_is_rejected(api: Api) -> None:
    """Scenario: NUL 문자가 있는 이름은 422다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_vendor(api, name="a\u0000b")
    # Then
    assert response.status_code == 422, response.text


async def test_renaming_a_solution_under_another_vendors_path_is_not_found(api: Api) -> None:
    """Scenario: 다른 Vendor 경로로 Solution 이름을 바꾸면 404이고 이름은 그대로다."""
    # Given
    sap = await given_vendor(api, "SAP", ["Cloud"])
    oracle = await given_vendor(api, "Oracle")
    # When
    response = await when_rename_solution(
        api, vendor_id=oracle.id, solution_id=sap.solutions["Cloud"], name="X"
    )
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    await then_vendors_are(api, [("Oracle", []), ("SAP", ["Cloud"])])
