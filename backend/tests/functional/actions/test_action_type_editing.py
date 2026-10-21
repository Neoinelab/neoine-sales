"""Feature: Action 수정에서도 유형은 목록에서 고르거나 이름으로 입력한다.

수정 요청의 유형 규칙은 등록과 같다(`test_action_type_choice.py`). 같은 유형이면 변경도
History도 없고, 유형만 바뀌어도 History 한 건이 남는다. 유형 이름을 바꿔도 이미 남은
History 문구는 그대로다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import then_action_type_is, then_detail_is
from tests.functional.steps.action_types import (
    UNKNOWN_MESSAGE,
    given_type_id,
    then_type_count_is,
    then_type_usage_is,
    when_rename_type,
)
from tests.functional.steps.actions import (
    SUMMARY,
    given_action,
    when_get_action,
    when_update_action,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    given_deal,
    history_rows,
    then_history_is,
    when_list_history,
)
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

WEBINAR_SUMMARY = "웨비나 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)"


async def test_editing_to_a_new_type_records_history(api: Api) -> None:
    """Scenario: 수정에서 유형만 새 이름으로 바꿔도 유형이 생기고 History 한 건이 남는다(AC-13)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"], action_type="미팅", memo="")
    # When
    response = await when_update_action(api, created["id"], action_type={"name": "웨비나"}, memo="")
    # Then
    then_status_is(response, 200)
    then_action_type_is(response, "웨비나")
    await then_type_usage_is(api, "웨비나", 1)
    await then_type_usage_is(api, "미팅", 0)
    newest = history_rows(await when_list_history(api, deal["code"]))[-1]
    assert newest == ("action", "Action", SUMMARY, f"수정: {WEBINAR_SUMMARY}")


async def test_editing_with_the_same_type_changes_nothing(api: Api) -> None:
    """Scenario: 같은 유형(id 또는 대소문자만 다른 이름)에 내용도 같으면 History가 없다(AC-13)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"], action_type="Demo2")
    rows_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    by_name = await when_update_action(api, created["id"], action_type={"name": " DEMO2 "})
    by_id = await when_update_action(
        api, created["id"], action_type={"id": created["action_type"]["id"]}
    )
    # Then
    then_status_is(by_name, 200)
    then_status_is(by_id, 200)
    assert history_rows(await when_list_history(api, deal["code"])) == rows_before
    await then_type_count_is(api, 9)
    stored = (await when_get_action(api, created["id"])).json()
    assert stored["updated_at"] == created["updated_at"]


async def test_editing_with_an_unknown_type_id_is_rejected(api: Api) -> None:
    """Scenario: 수정에서 없는 유형 id는 422이고 Action은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_update_action(api, created["id"], action_type={"id": MISSING_ID})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, UNKNOWN_MESSAGE)
    assert (await when_get_action(api, created["id"])).json()["action_type"] == created[
        "action_type"
    ]


async def test_a_failed_edit_leaves_no_new_type(api: Api) -> None:
    """Scenario: 수정이 다른 필드 오류로 실패하면 새 유형도 생기지 않는다(AC-11)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_update_action(
        api, created["id"], action_type={"name": "웨비나"}, action="   "
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_type_count_is(api, 8)


async def test_renamed_type_shows_on_actions_but_not_in_history(api: Api) -> None:
    """Scenario: 유형 이름을 바꿔도 이미 남은 History 문구는 그대로고 Action 응답은 새 이름이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"], action_type="미팅", memo="")
    meeting = await given_type_id(api, "미팅")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_rename_type(api, meeting, "회의")
    # Then
    then_status_is(response, 200)
    shown = await when_get_action(api, created["id"])
    then_action_type_is(shown, "회의")
    assert shown.json()["action_type"]["id"] == meeting
    await then_history_is(api, deal["code"], [("action", "Action", "", f"등록: {SUMMARY}")])
