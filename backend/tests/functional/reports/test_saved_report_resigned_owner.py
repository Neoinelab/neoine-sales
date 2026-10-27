"""Feature: 리포트를 만든 사용자가 퇴사해도 리포트는 남고 "이름(퇴사)"로 표시된다.

리포트를 만들거나 마지막에 수정한 사용자는 users 행과 연결되어 있어, 삭제하면 물리 삭제가 아니라
퇴사 처리된다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_body_is, then_status_is
from tests.functional.steps.saved_reports import (
    given_logged_in,
    given_logged_in_as_admin,
    given_report_overwritten,
    given_saved_report,
    given_users,
    when_get_report,
    when_list_reports,
    when_run_saved_report,
)
from tests.functional.steps.users import id_of, when_delete_user

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_user_with_a_report_is_resigned_not_deleted(api: Api) -> None:
    """Scenario: 리포트를 만든 사용자를 삭제하면 퇴사 처리되고 전체 목록에는 남는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    await given_saved_report(api, "alice 리포트")
    await given_logged_in_as_admin(api)
    alice_id = await id_of(api, "alice")
    # When
    response = await when_delete_user(api, alice_id)
    # Then
    then_status_is(response, 200)
    then_body_is(response, {"outcome": "resigned"})
    assert await id_of(api, "alice", status="resigned") == alice_id


async def test_user_who_last_edited_a_report_is_resigned_not_deleted(api: Api) -> None:
    """Scenario: 남의 리포트를 마지막에 수정한 사용자도 삭제하면 퇴사 처리된다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in(api, "bob")
    await given_report_overwritten(api, public, "공개", visibility="public")
    await given_logged_in_as_admin(api)
    bob_id = await id_of(api, "bob")
    # When
    response = await when_delete_user(api, bob_id)
    # Then
    then_body_is(response, {"outcome": "resigned"})


async def test_report_of_a_resigned_owner_is_listed_with_the_resigned_label(api: Api) -> None:
    """Scenario: 만든 사람이 퇴사해도 공개 리포트는 남고 만든 사람이 "이름(퇴사)"로 보인다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in_as_admin(api)
    await when_delete_user(api, await id_of(api, "alice"))
    await given_logged_in(api, "bob")
    # When
    response = await when_list_reports(api)
    # Then
    then_status_is(response, 200)
    (item,) = response.json()
    assert item["id"] == public["id"]
    assert item["owner"]["resigned"] is True
    assert item["owner"]["label"].endswith("(퇴사)")
    assert item["updated_by"]["label"] == item["owner"]["label"]


async def test_report_of_a_resigned_owner_can_still_be_opened_and_run(api: Api) -> None:
    """Scenario: 퇴사한 사람이 만든 공개 리포트를 다른 사용자가 열고 실행할 수 있다."""
    # Given
    await given_users(api, alice="sales", bob="user")
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in_as_admin(api)
    await when_delete_user(api, await id_of(api, "alice"))
    await given_logged_in(api, "bob")
    # When
    response = await when_run_saved_report(api, public["id"])
    # Then
    then_status_is(response, 200)
    assert (await when_get_report(api, public["id"])).json()["owner"]["resigned"] is True
    assert response.json()["total_count"] == 0
