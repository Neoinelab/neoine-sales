"""Feature: 작성자(sales)와 admin은 Next Action을 종료(수행/미수행)하고 되돌릴 수 있다.

종료할 때 받은 메모는 기존 Memo 뒤에 줄바꿈 한 개로 덧붙는다(비었으면 그대로). 종료 시각은 서버
시계이고 Open으로 되돌리면 null이 된다(Memo는 그대로). 상태가 바뀔 때마다 Deal History에 구분
action, 대상 "Next Action" 한 건이 남는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import same_instant, then_action_is_unchanged
from tests.functional.steps.actions import (
    given_action,
    given_action_by,
    given_deal_with_a_sales_owner,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import (
    given_deal,
    history_rows,
    when_get_deal,
    when_list_history,
)
from tests.functional.steps.next_action_status import (
    HISTORY_TARGET,
    OPEN_BEFORE,
    given_status_changed,
    then_action_status_is,
    then_status_response_is,
    when_change_status,
    when_change_status_as,
)
from tests.functional.steps.users import given_signed_in_session, id_of
from tests.support.functional_clock import active_clock

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _history_after_registration(api: Api, code: str) -> list[tuple[str, str, str, str]]:
    return history_rows(await when_list_history(api, code))[1:]


async def test_owner_closes_the_next_action_as_done_with_a_memo(api: Api) -> None:
    """Scenario: 작성자가 메모와 종료(수행)하면 Memo 뒤에 줄바꿈으로 덧붙고 종료 시각이 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_change_status(api, created["id"], "done", "견적 전달 완료")
    # Then
    then_status_response_is(response, "done", closed=True, memo="요구사항 정리\n견적 전달 완료")
    assert same_instant(response.json()["next_action_closed_at"], active_clock().now())
    await then_action_status_is(api, created["id"], "done", memo="요구사항 정리\n견적 전달 완료")


async def test_closing_with_an_empty_memo_uses_the_note_only(api: Api) -> None:
    """Scenario: 기존 Memo가 비어 있으면 종료 메모가 그대로 Memo가 된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"], memo="")
    # When
    response = await when_change_status(api, created["id"], "done", "  마무리  ")
    # Then
    then_status_response_is(response, "done", closed=True, memo="마무리")


@pytest.mark.parametrize("memo", [None, "", "   \n "])
async def test_closing_without_a_note_keeps_the_memo(api: Api, memo: str | None) -> None:
    """Scenario: 메모를 비우거나 보내지 않고 종료하면 Memo는 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_change_status(api, created["id"], "not_done", memo)
    # Then
    then_status_response_is(response, "not_done", closed=True, memo="요구사항 정리")


async def test_closing_records_one_history_entry_by_the_requester(api: Api) -> None:
    """Scenario: 종료하면 History에 구분 action, 대상 Next Action, 전후 문구 한 건이 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    rows_before = await _history_after_registration(api, deal["code"])
    # When
    response = await when_change_status(api, created["id"], "done", "전달 완료")
    # Then
    then_status_is(response, 200)
    rows = await _history_after_registration(api, deal["code"])
    assert rows == [
        *rows_before,
        ("action", HISTORY_TARGET, OPEN_BEFORE, "종료(수행) / Memo: 전달 완료"),
    ]


async def test_history_after_text_has_the_label_only_without_a_note(api: Api) -> None:
    """Scenario: 메모 없이 종료(미수행)하면 History의 후 문구는 라벨만이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    await when_change_status(api, created["id"], "not_done")
    # Then
    rows = await _history_after_registration(api, deal["code"])
    assert rows[-1] == ("action", HISTORY_TARGET, OPEN_BEFORE, "종료(미수행)")


async def test_admin_closes_another_users_action_and_is_the_history_actor(api: Api) -> None:
    """Scenario: admin은 다른 사람의 Action도 종료할 수 있고 History 변경자는 admin이다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    root = await id_of(api, "root")
    # When
    response = await when_change_status(api, created["id"], "done")
    # Then
    then_status_response_is(response, "done", closed=True)
    newest = (await when_list_history(api, deal["code"])).json()[0]
    assert (newest["category"], newest["target"], newest["by"]["id"]) == (
        "action",
        HISTORY_TARGET,
        root,
    )


async def test_owner_sales_closes_their_own_action(api: Api) -> None:
    """Scenario: 작성자 본인(sales)은 자기 세션으로 종료할 수 있다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    # When
    response = await when_change_status_as(api, kim, created["id"], "done", "내가 종료")
    # Then
    then_status_response_is(response, "done", closed=True, memo="요구사항 정리\n내가 종료")


async def test_reopening_clears_the_closed_time_and_keeps_the_memo(api: Api) -> None:
    """Scenario: 종료를 Open으로 되돌리면 종료 시각은 null이 되고 Memo는 그대로 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    await given_status_changed(api, created["id"], "done", "끝")
    # When
    response = await when_change_status(api, created["id"], "open")
    # Then
    then_status_response_is(response, "open", closed=False, memo="요구사항 정리\n끝")
    await then_action_status_is(api, created["id"], "open", memo="요구사항 정리\n끝")
    rows = await _history_after_registration(api, deal["code"])
    assert rows[-1] == (
        "action",
        HISTORY_TARGET,
        "요구사항 문서 전달 (Due 2027-01-15) · 종료(수행)",
        "Open",
    )


async def test_done_can_become_not_done_with_a_new_closed_time(api: Api) -> None:
    """Scenario: 종료(수행)에서 종료(미수행)으로 바꿀 수 있고 종료 시각이 새로 정해진다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    first = await given_status_changed(api, created["id"], "done")
    # When
    response = await when_change_status(api, created["id"], "not_done", "취소됨")
    # Then
    then_status_response_is(response, "not_done", closed=True, memo="요구사항 정리\n취소됨")
    assert not same_instant(
        response.json()["next_action_closed_at"], first["next_action_closed_at"]
    )


async def test_closing_does_not_change_the_other_fields_of_the_action(api: Api) -> None:
    """Scenario: 상태만 바뀌고 진행사항·Next Action·Due·수행 일시·담당자는 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_change_status(api, created["id"], "done")
    # Then
    body = response.json()
    for key in ("action", "next_action", "due_date", "acted_at", "actor", "status_key"):
        assert body[key] == created[key], key


async def test_changing_status_does_not_touch_the_deal(api: Api) -> None:
    """Scenario: Next Action 상태를 바꿔도 Deal 수정 시각은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    await when_change_status(api, created["id"], "done")
    # Then
    detail = (await when_get_deal(api, deal["code"])).json()
    assert same_instant(detail["updated_at"], deal["updated_at"])


async def test_a_failed_change_leaves_the_action_unchanged(api: Api) -> None:
    """Scenario: 이미 Open인 Action을 Open으로 바꾸려 하면 409이고 Action이 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_change_status(api, created["id"], "open")
    # Then
    then_status_is(response, 409)
    await then_action_is_unchanged(api, created)
