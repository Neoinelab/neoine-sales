"""Feature: Action 등록은 잘못된 입력·권한 없음·없는 Deal을 정해진 순서와 문구로 거절한다.

순서는 없는 Deal 404 -> 진행사항 -> Next Action -> Due Date(모두 422)이고, 아무것도 저장되지
않는다. 읽기 전용(user)은 403, 로그인하지 않으면 401이다. 수행 일시·담당자는 본문으로 보낼 수 없다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tests.functional.steps.actions import (
    DUE_DATE_REQUIRED,
    NEXT_ACTION_REQUIRED,
    PROGRESS_REQUIRED,
    READ_ONLY,
    action_body,
    then_deal_has_no_actions,
    then_detail_is,
    when_register_action,
    when_register_action_with_body,
)
from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.deals import NOT_FOUND, given_deal, then_history_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ABSENT_CODE = "20260101-ZZZZ"


@pytest.mark.parametrize(
    ("overrides", "detail"),
    [
        pytest.param({"action": "   "}, PROGRESS_REQUIRED, id="blank-progress"),
        pytest.param({"action": ""}, PROGRESS_REQUIRED, id="empty-progress"),
        pytest.param({"next_action": "  "}, NEXT_ACTION_REQUIRED, id="blank-next-action"),
        pytest.param({"due_date": None}, DUE_DATE_REQUIRED, id="null-due-date"),
        pytest.param(
            {"action": " ", "next_action": " ", "due_date": None},
            PROGRESS_REQUIRED,
            id="progress-is-reported-first",
        ),
        pytest.param(
            {"next_action": " ", "due_date": None},
            NEXT_ACTION_REQUIRED,
            id="next-action-before-due-date",
        ),
    ],
)
async def test_invalid_action_is_rejected_in_mock_order(
    api: Api, overrides: dict[str, object], detail: str
) -> None:
    """Scenario: 빈 값은 목업과 같은 순서·문구로 422이고 아무것도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], **overrides)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, detail)
    await then_deal_has_no_actions(api, deal["code"])
    await then_history_is(api, deal["code"], [])


async def test_a_missing_due_date_is_the_domain_message_not_a_schema_error(api: Api) -> None:
    """Scenario: Due Date를 아예 보내지 않아도 "Due Date를 입력하세요."로 거절된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    body = action_body()
    del body["due_date"]
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, DUE_DATE_REQUIRED)


@pytest.mark.parametrize("field", ["action", "next_action", "memo"])
async def test_nul_character_in_a_text_field_is_rejected(api: Api, field: str) -> None:
    """Scenario: NUL 문자가 든 텍스트는 500이 아니라 422 invalid-value다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], **{field: "가\x00나"})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_deal_has_no_actions(api, deal["code"])


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({"acted_at": "2026-03-02T10:00:00+09:00"}, id="acted-at"),
        pytest.param({"actor_user_id": "00000000-0000-4000-8000-000000000001"}, id="actor-user-id"),
        pytest.param({"actor": "박영업"}, id="free-text-actor"),
        pytest.param({"deal_code": "20261016-A001"}, id="deal-code"),
        pytest.param({"title": "구 필드"}, id="legacy-title"),
    ],
)
async def test_client_cannot_set_acted_at_or_actor(api: Api, extra: dict[str, object]) -> None:
    """Scenario: 수행 일시·담당자 같은 서버가 채우는 필드를 보내면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(api, deal["code"], action_body(**extra))
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_deal_has_no_actions(api, deal["code"])


@pytest.mark.parametrize(
    "action_type",
    [
        pytest.param("meeting", id="old-enum-value"),
        pytest.param("미팅", id="plain-name-string"),
        pytest.param(None, id="null"),
        pytest.param({}, id="neither-id-nor-name"),
        pytest.param({"id": str(uuid4()), "name": "미팅"}, id="both-id-and-name"),
        pytest.param({"id": "not-a-uuid"}, id="id-not-a-uuid"),
    ],
)
async def test_a_type_that_is_not_a_choice_object_is_a_request_validation_error(
    api: Api, action_type: object
) -> None:
    """Scenario: 유형이 문자열·null이거나 id·name 둘 다/하나도 없으면 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action_with_body(
        api, deal["code"], {**action_body(), "action_type": action_type}
    )
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_deal_has_no_actions(api, deal["code"])


async def test_a_missing_type_is_a_request_validation_error(api: Api) -> None:
    """Scenario: 유형을 아예 보내지 않으면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    body = action_body()
    del body["action_type"]
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("code", [ABSENT_CODE, "not-a-code"])
async def test_recording_on_a_missing_or_malformed_deal_is_not_found_before_validation(
    api: Api, code: str
) -> None:
    """Scenario: 없는 Deal이나 형식이 틀린 code는 입력이 잘못돼도 404가 먼저다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_action(api, code, action="  ", next_action="", due_date=None)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, NOT_FOUND)


async def test_viewer_cannot_record_an_action(api: Api) -> None:
    """Scenario: 읽기 전용(user) 계정은 Action을 남길 수 없다(403)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="user")
    # When
    response = await when_register_action(api, deal["code"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, READ_ONLY)
    await then_deal_has_no_actions(api, deal["code"])


async def test_anonymous_user_cannot_record_an_action(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401이다(본문 검증보다 먼저)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_out(api)
    # When
    response = await when_register_action(api, deal["code"], action="  ")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
