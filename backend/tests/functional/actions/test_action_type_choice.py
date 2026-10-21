"""Feature: Action의 유형은 목록에서 고르거나 이름으로 입력하고, 없는 이름은 새 유형이 된다.

요청의 유형은 `{"id": ...}`(있는 유형) 또는 `{"name": ...}`(대소문자 무시로 찾고, 없으면 같은
요청에서 만든다) 중 하나다. 등록·수정이 실패하면 새 유형도 생기지 않는다. 응답의 유형은
`{id, name}`이고 이름은 항상 지금 이름이다(이미 남은 History 문구는 바뀌지 않는다).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import (
    then_action_type_is,
    then_deal_has_no_actions,
    then_detail_is,
)
from tests.functional.steps.action_types import (
    DEFAULT_ORDER,
    REQUIRED_MESSAGE,
    TOO_LONG_MESSAGE,
    UNKNOWN_MESSAGE,
    given_type_created,
    given_type_id,
    given_type_list,
    then_type_count_is,
    then_type_usage_is,
)
from tests.functional.steps.actions import (
    action_body,
    given_action,
    when_register_action,
    when_register_action_with_body,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    NOT_FOUND,
    given_deal,
    given_my_user_id,
    then_history_is,
)
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

WEBINAR_SUMMARY = "웨비나 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)"


async def test_registering_with_an_id_uses_that_type(api: Api) -> None:
    """Scenario: 목록에서 고른 유형의 id를 보내면 그 유형이 저장된다(AC-7)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    demo = await given_type_id(api, "데모")
    # When
    response = await when_register_action(api, deal["code"], action_type={"id": demo})
    # Then
    then_status_is(response, 201)
    assert response.json()["action_type"] == {"id": demo, "name": "데모"}
    await then_type_count_is(api, 8)


async def test_registering_with_an_existing_name_reuses_the_type(api: Api) -> None:
    """Scenario: 기존 유형과 대소문자만 다른 이름은 그 유형을 쓰고 새로 만들지 않는다(AC-9)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    existing = await given_type_created(api, "Demo2")
    # When
    response = await when_register_action(api, deal["code"], action_type={"name": " demo2 "})
    # Then
    then_status_is(response, 201)
    assert response.json()["action_type"] == {"id": existing["id"], "name": "Demo2"}
    await then_type_count_is(api, 9)


async def test_registering_with_the_name_of_a_default_type_reuses_it(api: Api) -> None:
    """Scenario: 기본 유형의 이름을 입력해도 같은 유형이 쓰이고 새 유형은 생기지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    meeting = await given_type_id(api, "미팅")
    # When
    response = await when_register_action(api, deal["code"], action_type="  미팅 ")
    # Then
    then_status_is(response, 201)
    assert response.json()["action_type"] == {"id": meeting, "name": "미팅"}
    await then_type_count_is(api, 8)


async def test_registering_with_a_new_name_creates_the_type(api: Api) -> None:
    """Scenario: 목록에 없는 이름이면 같은 요청에서 새 유형이 생기고 만든 사람이 기록된다(AC-10)."""
    # Given
    await given_logged_in_as(api, role="sales")
    me = await given_my_user_id(api)
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action_type={"name": "  웨비나  "})
    # Then
    then_status_is(response, 201)
    then_action_type_is(response, "웨비나")
    created = [x for x in await given_type_list(api) if x["name"] == "웨비나"]
    assert len(created) == 1
    assert created[0]["id"] == response.json()["action_type"]["id"]
    assert created[0]["is_default"] is False
    assert created[0]["created_by"]["id"] == me  # type: ignore[index]
    assert [x["name"] for x in await given_type_list(api)] == [*DEFAULT_ORDER, "웨비나"]
    await then_type_usage_is(api, "웨비나", 1)


async def test_sales_registers_an_action_with_a_new_type_name_and_gets_an_integer_type_id(
    api: Api,
) -> None:
    """Scenario: 새 이름으로 등록하면 응답의 유형 id가 정수이고 유형 목록에 같은 id가 있다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action_type={"name": "웨비나"})
    # Then
    then_status_is(response, 201)
    type_id = response.json()["action_type"]["id"]
    assert type(type_id) is int
    assert type_id >= 1
    listed = [x for x in await given_type_list(api) if x["name"] == "웨비나"]
    assert [x["id"] for x in listed] == [type_id]
    assert type(listed[0]["id"]) is int


async def test_the_created_type_is_reused_by_the_next_action(api: Api) -> None:
    """Scenario: 같은 이름으로 다시 남기면 새로 만든 유형을 그대로 쓰고 유형은 하나뿐이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    first = await given_action(api, deal["code"], action_type="웨비나")
    # When
    second = await when_register_action(api, deal["code"], action_type="웨비나")
    # Then
    then_status_is(second, 201)
    assert second.json()["action_type"]["id"] == first["action_type"]["id"]
    await then_type_usage_is(api, "웨비나", 2)
    await then_type_count_is(api, 9)


async def test_unknown_type_id_is_rejected(api: Api) -> None:
    """Scenario: 없는 유형 id는 422이고 문구가 정해져 있으며 아무것도 저장되지 않는다(AC-8)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action_type={"id": MISSING_ID})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, UNKNOWN_MESSAGE)
    await then_deal_has_no_actions(api, deal["code"])
    await then_type_count_is(api, 8)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"action": "   ", "next_action": ""}, id="both-blank"),
        pytest.param({"due_date": None}, id="missing-due-date"),
        pytest.param({"next_action": "", "due_date": "2027-01-15"}, id="due-without-next-action"),
    ],
)
async def test_failed_registration_leaves_no_new_type(
    api: Api, overrides: dict[str, object]
) -> None:
    """Scenario: 다른 필드 오류로 등록이 실패하면 새 유형도 생기지 않는다(AC-11)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(
        api, deal["code"], action_type={"name": "웨비나"}, **overrides
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_type_count_is(api, 8)
    await then_deal_has_no_actions(api, deal["code"])


async def test_failed_status_change_leaves_no_new_type(api: Api) -> None:
    """Scenario: Status 동시 변경이 실패하면 Action도 새 유형도 남지 않는다(AC-11)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    body = action_body(
        action_type={"name": "웨비나"},
        status_change={"change": {"field": "status_key", "value": "contract_completed"}},
    )
    # When
    response = await when_register_action_with_body(api, deal["code"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_type_count_is(api, 8)
    await then_deal_has_no_actions(api, deal["code"])


async def test_a_missing_deal_fails_without_creating_a_type(api: Api) -> None:
    """Scenario: 없는 Deal은 유형 오류보다 먼저 404이고 새 유형도 생기지 않는다(AC-12)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_action(
        api, "20260101-ZZZZ", action_type={"name": "웨비나"}, action="  "
    )
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, NOT_FOUND)
    await then_type_count_is(api, 8)


@pytest.mark.parametrize(
    ("action_type", "message"),
    [
        pytest.param({"name": "   "}, REQUIRED_MESSAGE, id="blank-name"),
        pytest.param({"name": ""}, REQUIRED_MESSAGE, id="empty-name"),
        pytest.param({"name": "가" * 51}, TOO_LONG_MESSAGE, id="51-chars"),
    ],
)
async def test_type_errors_are_reported_before_the_progress_error(
    api: Api, action_type: dict[str, str], message: str
) -> None:
    """Scenario: 유형 오류는 진행사항 오류보다 먼저 나온다(AC-3·12)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action_type=action_type, action="  ")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, message)


async def test_a_type_name_of_50_characters_is_accepted_and_a_nul_is_rejected(api: Api) -> None:
    """Scenario: 50자 이름은 통과하고 NUL이 든 이름은 서버 오류 없이 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    accepted = await when_register_action(api, deal["code"], action_type={"name": "가" * 50})
    rejected = await when_register_action(api, deal["code"], action_type={"name": "웨\x00비나"})
    # Then
    then_status_is(accepted, 201)
    then_problem_is(rejected, status=422, type_suffix="invalid-value")


async def test_history_uses_the_name_of_the_chosen_type(api: Api) -> None:
    """Scenario: History 문구의 유형 자리에 고른(또는 새로 만든) 유형의 이름이 들어간다(AC-15)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action_type="웨비나", memo="")
    # Then
    then_status_is(response, 201)
    await then_history_is(api, deal["code"], [("action", "Action", "", f"등록: {WEBINAR_SUMMARY}")])
