"""Feature: Vendor의 id는 JSON 정수이고 만든 순서대로 커진다.

새 항목은 시퀀스 번호를 받으므로 나중에 만든 항목의 id가 더 크다. 경로의 id로 이름을 바꿀 수
있다(정수 id가 URL로 그대로 통한다).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.vendors import (
    when_create_vendor,
    when_list_vendors,
    when_rename_vendor,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_sees_increasing_integer_ids_for_new_vendors(api: Api) -> None:
    """Scenario: Vendor 2개를 만들면 id가 정수이고 먼저 만든 것이 더 작으며 id로 이름을 바꾼다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    first = await when_create_vendor(api, name="SAP")
    second = await when_create_vendor(api, name="Oracle")
    # Then
    for response in (first, second):
        then_status_is(response, 201)
        assert type(response.json()["id"]) is int
    assert 1 <= first.json()["id"] < second.json()["id"]
    renamed = await when_rename_vendor(api, vendor_id=first.json()["id"], name="SAP Korea")
    then_status_is(renamed, 200)
    assert renamed.json()["id"] == first.json()["id"]


async def test_the_vendor_list_carries_integer_ids(api: Api) -> None:
    """Scenario: 목록 응답의 Vendor id가 정수이고 Solution 목록은 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await when_create_vendor(api, name="SAP")
    # When
    response = await when_list_vendors(api)
    # Then
    then_status_is(response, 200)
    (listed,) = response.json()
    assert type(listed["id"]) is int
    assert "solutions" not in listed
