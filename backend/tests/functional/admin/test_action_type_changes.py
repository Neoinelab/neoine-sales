"""Feature: admin은 Action 유형의 이름을 바꾸고 쓰지 않는 유형을 지운다.

기본 유형도 이름 변경·삭제 대상이다. 쓰는 Action이 있으면 삭제할 수 없고(409, 건수 문구) 이름은 바꿀
수 있다. sales·user의 변경·삭제는 403이다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_types import (
    ADMIN_REQUIRED,
    DEFAULT_ORDER,
    DUPLICATE_MESSAGE,
    REQUIRED_MESSAGE,
    TOO_LONG_MESSAGE,
    given_type_created,
    given_type_id,
    then_type_count_is,
    then_type_names_are,
    then_type_usage_is,
    when_create_type,
    when_delete_type,
    when_rename_type,
)
from tests.functional.steps.actions import given_action, given_deal_with_a_sales_owner
from tests.functional.steps.auth import RoleName, given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_renames_a_default_type_and_keeps_its_place(api: Api) -> None:
    """Scenario: admin이 기본 유형의 이름을 바꾸면 순서는 그대로이고 기본 표시도 유지된다(AC-5)."""
    # Given
    await given_logged_in_as(api, role="admin")
    meeting = await given_type_id(api, "미팅")
    # When
    response = await when_rename_type(api, meeting, "  회의  ")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, id=meeting, name="회의", is_default=True)
    await then_type_names_are(api, ["통화", "회의", *DEFAULT_ORDER[2:]])


async def test_renaming_only_the_case_of_its_own_name_is_allowed(api: Api) -> None:
    """Scenario: 자기 이름의 대소문자만 바꾸는 것은 허용된다(AC-4)."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_type_created(api, "Webinar")
    # When
    response = await when_rename_type(api, created["id"], "WEBINAR")
    # Then
    then_status_is(response, 200)
    assert response.json()["name"] == "WEBINAR"


async def test_renaming_to_another_types_name_conflicts(api: Api) -> None:
    """Scenario: 다른 유형과 대소문자만 다른 이름으로 바꾸면 409이고 이름은 그대로다(AC-4)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_type_created(api, "Webinar")
    demo = await given_type_id(api, "데모")
    # When
    response = await when_rename_type(api, demo, "webinar")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_MESSAGE
    assert await given_type_id(api, "데모") == demo


@pytest.mark.parametrize(
    ("name", "message"),
    [("   ", REQUIRED_MESSAGE), ("가" * 51, TOO_LONG_MESSAGE)],
    ids=["blank", "51-chars"],
)
async def test_renaming_to_an_invalid_name_is_rejected(api: Api, name: str, message: str) -> None:
    """Scenario: 공백뿐이거나 51자인 새 이름은 422이고 이름은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    demo = await given_type_id(api, "데모")
    # When
    response = await when_rename_type(api, demo, name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == message
    await then_type_names_are(api, DEFAULT_ORDER)


async def test_renaming_or_deleting_an_unknown_type_is_not_found(api: Api) -> None:
    """Scenario: 없는 id의 이름 변경·삭제는 404다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    renamed = await when_rename_type(api, MISSING_ID, "무엇")
    deleted = await when_delete_type(api, MISSING_ID)
    # Then
    then_problem_is(renamed, status=404, type_suffix="not-found")
    then_problem_is(deleted, status=404, type_suffix="not-found")


async def test_admin_deletes_an_unused_type_even_when_it_is_a_default(api: Api) -> None:
    """Scenario: 쓰는 Action이 없으면 기본 유형도 삭제된다(204)."""
    # Given
    await given_logged_in_as(api, role="admin")
    demo = await given_type_id(api, "데모")
    # When
    response = await when_delete_type(api, demo)
    # Then
    then_status_is(response, 204)
    await then_type_names_are(api, [n for n in DEFAULT_ORDER if n != "데모"])


async def test_a_deleted_name_can_be_used_again(api: Api) -> None:
    """Scenario: 지운 유형의 이름은 다시 만들 수 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_type_created(api, "웨비나")
    await when_delete_type(api, created["id"])
    # When
    response = await when_create_type(api, "웨비나")
    # Then
    then_status_is(response, 201)


async def test_used_type_cannot_be_deleted(api: Api) -> None:
    """Scenario: 쓰는 Action이 있는 유형의 삭제는 409(Action 건수)이고 유형은 남는다(AC-6)."""
    # Given
    await given_logged_in_as(api, role="admin")
    deal = await given_deal_with_a_sales_owner(api)
    await given_action(api, deal["code"], action_type="미팅")
    await given_action(api, deal["code"], action_type="미팅")
    meeting = await given_type_id(api, "미팅")
    # When
    response = await when_delete_type(api, meeting)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == "사용 중인 유형은 삭제할 수 없습니다. (Action 2건)"
    await then_type_usage_is(api, "미팅", 2)


async def test_usage_count_is_the_number_of_actions_using_the_type(api: Api) -> None:
    """Scenario: 목록의 usage_count는 그 유형을 쓰는 Action 건수이고, 이름을 바꿔도 같다(AC-1·5)."""
    # Given
    await given_logged_in_as(api, role="admin")
    deal = await given_deal_with_a_sales_owner(api)
    await given_action(api, deal["code"], action_type="미팅")
    await given_action(api, deal["code"], action_type="미팅")
    await given_action(api, deal["code"], action_type="데모")
    meeting = await given_type_id(api, "미팅")
    # When
    response = await when_rename_type(api, meeting, "회의")
    # Then
    then_status_is(response, 200)
    assert response.json()["usage_count"] == 2
    await then_type_usage_is(api, "회의", 2)
    await then_type_usage_is(api, "데모", 1)
    await then_type_usage_is(api, "통화", 0)


async def test_a_type_becomes_deletable_when_its_last_action_is_gone(api: Api) -> None:
    """Scenario: 쓰던 Action을 모두 지우면 유형을 삭제할 수 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    deal = await given_deal_with_a_sales_owner(api)
    action = await given_action(api, deal["code"], action_type="미팅")
    await api.delete(f"/api/v1/deal-actions/{action['id']}")
    # When
    response = await when_delete_type(api, await given_type_id(api, "미팅"))
    # Then
    then_status_is(response, 204)


@pytest.mark.parametrize("role", ["sales", "user"])
async def test_only_admin_renames_or_deletes(api: Api, role: RoleName) -> None:
    """Scenario: sales·user의 이름 변경·삭제는 403이고 유형은 그대로다(AC-6)."""
    # Given
    await given_logged_in_as(api, role="admin")
    demo = await given_type_id(api, "데모")
    await given_logged_in_as(api, role=role)
    # When
    renamed = await when_rename_type(api, demo, "시연")
    deleted = await when_delete_type(api, demo)
    # Then
    then_status_is(renamed, 403)
    then_status_is(deleted, 403)
    if role == "sales":
        assert renamed.json()["detail"] == ADMIN_REQUIRED
        assert deleted.json()["detail"] == ADMIN_REQUIRED
    await then_type_names_are(api, DEFAULT_ORDER)


async def test_anonymous_user_cannot_rename_or_delete(api: Api) -> None:
    """Scenario: 로그인하지 않으면 이름 변경·삭제가 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    demo = await given_type_id(api, "데모")
    await given_logged_out(api)
    # When
    renamed = await when_rename_type(api, demo, "시연")
    deleted = await when_delete_type(api, demo)
    # Then
    then_problem_is(renamed, status=401, type_suffix="unauthenticated")
    then_problem_is(deleted, status=401, type_suffix="unauthenticated")
    await given_logged_in_as(api, role="admin")
    await then_type_count_is(api, 8)
