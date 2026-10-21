"""Feature: Vendor·Solution의 id는 JSON 정수이고 만든 순서대로 커진다.

새 항목은 시퀀스 번호를 받으므로 같은 종류에서 나중에 만든 항목의 id가 더 크다. 경로의 id로 이름을
바꿀 수 있다(정수 id가 URL로 그대로 통한다).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.vendors import (
    when_create_solution,
    when_create_vendor,
    when_list_vendors,
    when_rename_solution,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_sees_increasing_integer_ids_for_new_vendors_and_solutions(api: Api) -> None:
    """Scenario: Vendor 2개와 Solution 1개를 만들면 id가 정수이고 먼저 만든 것이 더 작다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    first = await when_create_vendor(api, name="SAP")
    second = await when_create_vendor(api, name="Oracle")
    solution = await when_create_solution(api, vendor_id=first.json()["id"], name="S/4HANA")
    # Then
    for response in (first, second, solution):
        then_status_is(response, 201)
        assert type(response.json()["id"]) is int
    assert 1 <= first.json()["id"] < second.json()["id"]
    assert type(solution.json()["vendor_id"]) is int
    assert solution.json()["vendor_id"] == first.json()["id"]
    renamed = await when_rename_solution(
        api,
        vendor_id=first.json()["id"],
        solution_id=solution.json()["id"],
        name="S/4HANA Cloud",
    )
    then_status_is(renamed, 200)
    assert renamed.json()["id"] == solution.json()["id"]


async def test_the_vendor_list_carries_integer_ids_everywhere(api: Api) -> None:
    """Scenario: 목록 응답의 Vendor id·Solution id·Solution의 vendor_id가 모두 정수다."""
    # Given
    await given_logged_in_as(api, role="admin")
    vendor = await when_create_vendor(api, name="SAP")
    await when_create_solution(api, vendor_id=vendor.json()["id"], name="S/4HANA")
    # When
    response = await when_list_vendors(api)
    # Then
    then_status_is(response, 200)
    (listed,) = response.json()
    assert type(listed["id"]) is int
    (solution,) = listed["solutions"]
    assert type(solution["id"]) is int
    assert solution["vendor_id"] == listed["id"]
