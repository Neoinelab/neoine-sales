"""Feature: Next Action 상태 변경은 권한·규칙에 맞지 않으면 거절하고 아무것도 바꾸지 않는다.

판정 순서는 요청 검증 422 -> 없는 Action 404 -> 작성자가 아닌 sales 403 -> 도메인 입력 422
(Open으로 되돌리며 메모, NUL) -> 409(Next Action 없음, 같은 상태)다. 읽기 전용(user)은 403,
로그인하지 않으면 401이다. 거절되면 Memo·상태·종료 시각·History가 그대로다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import then_action_is_unchanged, then_detail_is
from tests.functional.steps.actions import (
    NOT_FOUND,
    READ_ONLY,
    given_action,
    given_action_by,
    given_deal_with_a_sales_owner,
)
from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.deals import given_deal, history_rows, when_list_history
from tests.functional.steps.next_action_status import (
    NO_NEXT_ACTION,
    STATUS_FORBIDDEN,
    given_progress_only_action,
    given_status_changed,
    when_change_status,
    when_change_status_as,
    when_change_status_with_body,
)
from tests.functional.steps.users import given_signed_in_session
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ABSENT_ID = MISSING_ID


async def test_another_sales_cannot_change_the_status(api: Api) -> None:
    """Scenario: 작성자가 아닌 sales의 요청은 403이고 Action·History는 그대로다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    history_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    response = await when_change_status_as(api, park, created["id"], "done", "남의 것")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, STATUS_FORBIDDEN)
    await then_action_is_unchanged(api, created)
    assert history_rows(await when_list_history(api, deal["code"])) == history_before


async def test_viewer_cannot_change_the_status(api: Api) -> None:
    """Scenario: 읽기 전용(user) 계정의 요청은 403(읽기 전용 문구)이고 Action은 그대로다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    created = await given_action_by(api, kim, deal["code"])
    await given_logged_in_as(api, role="user")
    # When
    response = await when_change_status(api, created["id"], "done")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, READ_ONLY)
    await then_action_is_unchanged(api, created)


async def test_anonymous_user_cannot_change_the_status(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    await given_logged_out(api)
    # When
    response = await when_change_status(api, created["id"], "done")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_a_missing_action_is_not_found_before_the_owner_check(api: Api) -> None:
    """Scenario: 없는 Action은 작성자 확인보다 먼저 404다."""
    # Given
    park = await given_signed_in_session(api, login_id="park", role="sales")
    # When
    response = await when_change_status_as(api, park, ABSENT_ID, "done")
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, NOT_FOUND)


async def test_the_same_status_is_a_conflict(api: Api) -> None:
    """Scenario: 이미 Open인 Action을 Open으로 바꾸면 409 invalid-state이고 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_change_status(api, created["id"], "open", None)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, "이미 Open 상태입니다.")
    await then_action_is_unchanged(api, created)


async def test_closing_an_already_closed_action_with_the_same_status_keeps_memo_and_history(
    api: Api,
) -> None:
    """Scenario: 종료(수행)를 다시 종료(수행)하려 하면 409이고 Memo·History가 더 늘지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    closed = await given_status_changed(api, created["id"], "done", "첫 종료")
    history_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    response = await when_change_status(api, created["id"], "done", "또 종료")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, "이미 종료(수행) 상태입니다.")
    await then_action_is_unchanged(api, closed)
    assert history_rows(await when_list_history(api, deal["code"])) == history_before


async def test_an_action_without_a_next_action_cannot_change_status(api: Api) -> None:
    """Scenario: Next Action이 없는 Action은 상태를 바꿀 수 없다(409). Memo·History는 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_progress_only_action(api, deal["code"])
    history_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    response = await when_change_status(api, created["id"], "done", "메모")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, NO_NEXT_ACTION)
    await then_action_is_unchanged(api, created)
    assert history_rows(await when_list_history(api, deal["code"])) == history_before


async def test_reopening_with_a_memo_is_rejected(api: Api) -> None:
    """Scenario: Open으로 되돌리면서 메모를 보내면 422이고 종료 상태가 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    closed = await given_status_changed(api, created["id"], "done")
    # When
    response = await when_change_status(api, created["id"], "open", "되돌리며 메모")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_action_is_unchanged(api, closed)


async def test_a_memo_with_a_nul_character_is_rejected(api: Api) -> None:
    """Scenario: 종료 메모에 NUL 문자가 있으면 500이 아니라 422 invalid-value다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_change_status(api, created["id"], "done", "가\x00나")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_action_is_unchanged(api, created)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="missing-status"),
        pytest.param({"status": "closed"}, id="filter-value-is-not-a-status"),
        pytest.param({"status": "notDone"}, id="camel-case"),
        pytest.param({"status": "DONE"}, id="upper-case"),
        pytest.param({"status": None}, id="null-status"),
        pytest.param({"status": "done", "memo": 1}, id="memo-not-a-string"),
        pytest.param({"status": "done", "closed_at": "2027-01-01T00:00:00Z"}, id="server-field"),
    ],
)
async def test_a_malformed_body_is_a_request_validation_error(api: Api, body: object) -> None:
    """Scenario: 상태 값·본문 형식이 틀리면 422 request-validation이고 Action은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    # When
    response = await when_change_status_with_body(api, created["id"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_action_is_unchanged(api, created)
