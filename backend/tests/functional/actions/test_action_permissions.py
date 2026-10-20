"""Feature: Action 수정·삭제는 담당자 본인(sales)과 admin만 할 수 있다.

판정 순서는 401 -> 읽기 전용(user) 403 -> 없는 id 404 -> 담당자가 아닌 sales 403 -> 내용 검증
422다. 다른 sales의 403은 본문이 잘못되어도 403이고 Action·History는 그대로다. 조회는 로그인한 모든
역할이 할 수 있다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import (
    then_action_is_gone,
    then_action_is_unchanged,
    then_body_has,
    then_detail_is,
)
from tests.functional.steps.actions import (
    DELETE_FORBIDDEN,
    EDIT_FORBIDDEN,
    NOT_FOUND,
    READ_ONLY,
    given_action_by,
    given_deal_with_a_sales_owner,
    when_delete_action,
    when_delete_action_as,
    when_get_action,
    when_list_actions,
    when_update_action,
    when_update_action_as,
)
from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import history_rows, when_list_history
from tests.functional.steps.users import given_signed_in_session, id_of

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ABSENT_ID = "6f1c1b3a-0000-4000-8000-000000000001"


async def test_admin_edits_and_deletes_another_users_action(api: Api) -> None:
    """Scenario: admin은 다른 사람의 Action을 고칠 수 있고 History에는 admin이 변경자로 남는다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    root = await id_of(api, "root")
    # When
    response = await when_update_action(api, created["id"], action="admin이 고침")
    # Then
    then_status_is(response, 200)
    then_body_has(response, action="admin이 고침", actor=created["actor"])
    newest = (await when_list_history(api, deal["code"])).json()[0]
    assert (newest["category"], newest["by"]["id"]) == ("action", root)


async def test_admin_deletes_another_users_action(api: Api) -> None:
    """Scenario: admin은 다른 사람의 Action을 지울 수 있고 History에는 admin이 남는다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    root = await id_of(api, "root")
    # When
    response = await when_delete_action(api, created["id"])
    # Then
    then_status_is(response, 204)
    await then_action_is_gone(api, created["id"])
    newest = (await when_list_history(api, deal["code"])).json()[0]
    assert (newest["after"], newest["by"]["id"]) == ("삭제", root)


async def test_action_owner_edits_regardless_of_who_owns_the_deal(api: Api) -> None:
    """Scenario: 수정 권한은 Deal Owner가 아니라 Action 담당자 기준이다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)  # Owner는 kim이 아니어도 된다
    created = await given_action_by(api, kim, deal["code"])
    # When
    response = await when_update_action_as(api, kim, created["id"], memo="본인이 고침")
    # Then
    then_status_is(response, 200)
    then_body_has(response, memo="본인이 고침")


async def test_another_sales_cannot_edit_an_action(api: Api) -> None:
    """Scenario: 담당자가 아닌 sales가 고치려 하면 403이고 Action·History는 그대로다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    history_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    response = await when_update_action_as(api, park, created["id"], action="남이 고침")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, EDIT_FORBIDDEN)
    await then_action_is_unchanged(api, created)
    assert history_rows(await when_list_history(api, deal["code"])) == history_before


async def test_another_sales_cannot_delete_an_action(api: Api) -> None:
    """Scenario: 담당자가 아닌 sales가 지우려 하면 403이고 Action·History는 그대로다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    history_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    response = await when_delete_action_as(api, park, created["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, DELETE_FORBIDDEN)
    await then_action_is_unchanged(api, created)
    assert history_rows(await when_list_history(api, deal["code"])) == history_before


async def test_another_sales_with_a_bad_body_gets_403_not_422(api: Api) -> None:
    """Scenario: 권한이 없는 사람에게는 본문이 잘못돼도 검증 오류가 아니라 403이 나간다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    # When
    response = await when_update_action_as(api, park, created["id"], action="   ", due_date=None)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, EDIT_FORBIDDEN)


async def test_a_missing_action_is_not_found_before_the_owner_check(api: Api) -> None:
    """Scenario: 없는 Action은 담당자 확인보다 먼저 404다."""
    # Given
    park = await given_signed_in_session(api, login_id="park", role="sales")
    # When
    response = await when_update_action_as(api, park, ABSENT_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, NOT_FOUND)


async def test_a_missing_action_cannot_be_deleted_by_another_sales_either(api: Api) -> None:
    """Scenario: 없는 Action의 삭제도 404다."""
    # Given
    park = await given_signed_in_session(api, login_id="park", role="sales")
    # When
    response = await when_delete_action_as(api, park, ABSENT_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, NOT_FOUND)


async def test_viewer_cannot_edit_an_action(api: Api) -> None:
    """Scenario: 읽기 전용(user) 계정의 수정은 403(읽기 전용 문구)이고 Action은 그대로다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    await given_logged_in_as(api, role="user")
    # When
    response = await when_update_action(api, created["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, READ_ONLY)
    await then_action_is_unchanged(api, created)


async def test_viewer_cannot_delete_an_action(api: Api) -> None:
    """Scenario: 읽기 전용(user) 계정의 삭제는 403(읽기 전용 문구)이고 Action은 그대로다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    await given_logged_in_as(api, role="user")
    # When
    response = await when_delete_action(api, created["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, READ_ONLY)
    await then_action_is_unchanged(api, created)


async def test_viewer_is_refused_even_for_a_missing_action(api: Api) -> None:
    """Scenario: 읽기 전용 계정의 403이 없는 id의 404보다 먼저다."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_delete_action(api, ABSENT_ID)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, READ_ONLY)


async def test_anonymous_user_cannot_edit_an_action(api: Api) -> None:
    """Scenario: 로그인하지 않으면 수정은 401이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_logged_out(api)
    # When
    response = await when_update_action(api, ABSENT_ID)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_anonymous_user_cannot_delete_an_action(api: Api) -> None:
    """Scenario: 로그인하지 않으면 삭제는 401이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_logged_out(api)
    # When
    response = await when_delete_action(api, ABSENT_ID)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_every_role_can_read_actions(api: Api) -> None:
    """Scenario: 읽기 전용 계정도 Deal의 Action 목록과 한 건 조회가 된다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    await given_logged_in_as(api, role="user")
    # When
    listed = await when_list_actions(api, deal["code"])
    # Then
    then_status_is(listed, 200)
    assert [item["id"] for item in listed.json()["items"]] == [created["id"]]
    then_status_is(await when_get_action(api, created["id"]), 200)
