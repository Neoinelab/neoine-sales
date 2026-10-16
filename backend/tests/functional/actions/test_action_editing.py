"""Feature: 영업은 자기 Action을 고치고 지우며, 변경은 Deal History에 남는다.

수정은 내용(유형·진행사항·Next Action·Due Date·Memo)만 바꾸고 수행 일시·담당자·스냅숏은 그대로다.
내용이 하나도 바뀌지 않으면 History도 수정 시각도 그대로다. 삭제는 물리 삭제이고, 가장 최근
Action을 지우면 Deal의 next_action이 그 이전 Action으로 돌아간다. 권한은 test_action_permissions다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import (
    SUMMARY_WITH_MEMO,
    action_body,
    given_action,
    names_of,
    same_instant,
    then_action_is_gone,
    then_action_is_unchanged,
    then_body_has,
    then_detail_is,
    when_delete_action,
    when_get_action,
    when_list_actions,
    when_update_action,
    when_update_action_with_body,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    given_deal,
    given_my_user_id,
    then_history_is,
    when_get_deal,
    when_list_history,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

AFTER = "수정: 제안 · 제안 발표 / Next Action: 견적 회신 (Due 2027-02-01) / Memo: 변경"
CHANGE = {
    "action_type": "proposal",
    "action": "제안 발표",
    "next_action": "견적 회신",
    "due_date": "2027-02-01",
    "memo": "변경",
}


async def test_action_owner_edits_a_previous_action(api: Api) -> None:
    """Scenario: 담당자가 이전 Action을 고치면 내용만 바뀌고 수행 일시·담당자는 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    me = await given_my_user_id(api)
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_update_action(api, created["id"], **CHANGE)
    # Then
    then_status_is(response, 200)
    then_body_has(response, **CHANGE, actor=created["actor"], deal_code=deal["code"])
    assert same_instant(response.json()["acted_at"], created["acted_at"])
    assert same_instant(response.json()["created_at"], created["created_at"])
    assert not same_instant(response.json()["updated_at"], created["updated_at"])
    stored = (await when_get_action(api, created["id"])).json()
    assert stored["action"] == "제안 발표"
    newest = (await when_list_history(api, deal["code"])).json()[0]
    assert (newest["category"], newest["target"]) == ("action", "Action")
    assert (newest["before"], newest["after"]) == (SUMMARY_WITH_MEMO, AFTER)
    assert newest["by"]["id"] == me


async def test_unchanged_edit_leaves_no_history(api: Api) -> None:
    """Scenario: 내용이 바뀌지 않은 수정은 200이지만 History도 수정 시각도 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_update_action(api, created["id"])
    # Then
    then_status_is(response, 200)
    assert same_instant(response.json()["updated_at"], created["updated_at"])
    await then_history_is(
        api, deal["code"], [("action", "Action", "", f"등록: {SUMMARY_WITH_MEMO}")]
    )


async def test_edit_equal_after_trimming_is_not_a_change(api: Api) -> None:
    """Scenario: 앞뒤 공백만 다른 수정은 변경이 아니다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_update_action(
        api, created["id"], action="  킥오프 미팅  ", memo=" 요구사항 정리 "
    )
    # Then
    then_status_is(response, 200)
    assert same_instant(response.json()["updated_at"], created["updated_at"])
    await then_history_is(
        api, deal["code"], [("action", "Action", "", f"등록: {SUMMARY_WITH_MEMO}")]
    )


@pytest.mark.parametrize(
    ("overrides", "detail"),
    [
        pytest.param({"action": "   "}, "진행사항을 입력하세요.", id="blank-progress"),
        pytest.param({"next_action": ""}, "Next Action을 입력하세요.", id="empty-next-action"),
        pytest.param({"due_date": None}, "Due Date를 입력하세요.", id="null-due-date"),
    ],
)
async def test_edit_with_invalid_content_is_rejected_and_changes_nothing(
    api: Api, overrides: dict[str, object], detail: str
) -> None:
    """Scenario: 빈 값으로 고치려 하면 목업과 같은 문구의 422이고 Action은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_update_action(api, created["id"], **overrides)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, detail)
    await then_action_is_unchanged(api, created)


async def test_long_edit_is_saved_in_full(api: Api) -> None:
    """Scenario: 수정에도 길이 상한이 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_update_action(api, created["id"], action="가" * 5_000, memo="메" * 20_000)
    # Then
    then_status_is(response, 200)
    stored = (await when_get_action(api, created["id"])).json()
    assert (len(stored["action"]), len(stored["memo"])) == (5_000, 20_000)


async def test_edit_cannot_carry_a_status_change_or_server_filled_fields(api: Api) -> None:
    """Scenario: 수정 본문에 status_change나 수행 일시를 보내면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    body = action_body(status_change={"change": {"field": "status_key", "value": "best"}})
    # When
    response = await when_update_action_with_body(api, created["id"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_action_is_unchanged(api, created)


async def test_deleting_the_latest_action_moves_next_action_back(api: Api) -> None:
    """Scenario: 가장 최근 Action을 지우면 Deal의 next_action이 이전 Action으로 돌아간다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_action(
        api, deal["code"], action="먼저", next_action="먼저 할 일", due_date="2027-03-01"
    )
    latest = await given_action(
        api, deal["code"], action="나중", next_action="나중 할 일", due_date="2027-04-01"
    )
    # When
    response = await when_delete_action(api, latest["id"])
    # Then
    then_status_is(response, 204)
    await then_action_is_gone(api, latest["id"])
    detail = (await when_get_deal(api, deal["code"])).json()
    assert detail["next_action"] == {"text": "먼저 할 일", "due_date": "2027-03-01"}
    assert names_of(await when_list_actions(api, deal["code"])) == ["먼저"]


async def test_deleting_an_action_logs_the_summary_and_the_word_deleted(api: Api) -> None:
    """Scenario: 삭제하면 History에 삭제 전 요약과 "삭제"가 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    me = await given_my_user_id(api)
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_delete_action(api, created["id"])
    # Then
    then_status_is(response, 204)
    newest = (await when_list_history(api, deal["code"])).json()[0]
    assert (newest["category"], newest["before"], newest["after"]) == (
        "action",
        SUMMARY_WITH_MEMO,
        "삭제",
    )
    assert newest["by"]["id"] == me


async def test_deleting_the_only_action_leaves_no_next_action(api: Api) -> None:
    """Scenario: 하나뿐인 Action을 지우면 Deal의 next_action이 null이 된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_delete_action(api, created["id"])
    # Then
    then_status_is(response, 204)
    assert (await when_get_deal(api, deal["code"])).json()["next_action"] is None


async def test_deleting_an_action_twice_is_not_found_the_second_time(api: Api) -> None:
    """Scenario: 이미 지운 Action을 다시 지우면 404다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    await when_delete_action(api, created["id"])
    # When
    response = await when_delete_action(api, created["id"])
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
