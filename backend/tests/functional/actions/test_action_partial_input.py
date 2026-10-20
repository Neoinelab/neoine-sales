"""Feature: 영업은 진행사항만, Next Action만, 또는 둘 다 입력해 Action을 남기고 고칠 수 있다.

Next Action이 있는 Action만 상태(Open/종료)를 가진다. Next Action이 없으면 Due Date도 없고 상태도
null이다. 수정으로 Next Action을 비우면 상태·종료 시각이 사라지고, 없던 Next Action을 채우면 Open이
되며, 있던 Next Action의 내용만 바꾸면 종료 상태도 그대로다. 형식이 틀리면 422다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import (
    then_action_is_unchanged,
    then_body_has,
    then_deal_has_no_actions,
    then_detail_is,
)
from tests.functional.steps.actions import (
    ACTION_OR_NEXT_REQUIRED,
    DUE_DATE_REQUIRED,
    DUE_WITHOUT_NEXT,
    given_action,
    when_register_action,
    when_update_action,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import given_deal, then_history_is
from tests.functional.steps.next_action_status import (
    given_next_only_action,
    given_progress_only_action,
    given_status_changed,
    then_action_status_is,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_register_progress_only_action(api: Api) -> None:
    """Scenario: 진행사항만 있는 Action이 저장되고 Next Action 관련 값은 모두 null이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], next_action="", memo="")
    # Then
    then_status_is(response, 201)
    then_body_has(
        response,
        action="킥오프 미팅",
        next_action=None,
        due_date=None,
        next_action_status=None,
        next_action_closed_at=None,
    )
    await then_action_status_is(api, response.json()["id"], None)
    await then_history_is(api, deal["code"], [("action", "Action", "", "등록: 미팅 · 킥오프 미팅")])


async def test_register_next_only_action(api: Api) -> None:
    """Scenario: 진행사항 없이 Next Action과 Due Date만 있는 Action은 Open으로 저장된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action="", memo="")
    # Then
    then_status_is(response, 201)
    then_body_has(
        response,
        action=None,
        next_action="요구사항 문서 전달",
        due_date="2027-01-15",
        next_action_status="open",
        next_action_closed_at=None,
    )
    await then_history_is(
        api,
        deal["code"],
        [
            (
                "action",
                "Action",
                "",
                "등록: 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)",
            )
        ],
    )


async def test_register_with_both_parts_opens_the_next_action(api: Api) -> None:
    """Scenario: 둘 다 입력한 Action은 기존처럼 저장되고 Next Action은 Open이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"])
    # Then
    then_status_is(response, 201)
    then_body_has(response, action="킥오프 미팅", next_action_status="open")


async def test_register_with_neither_part_is_rejected(api: Api) -> None:
    """Scenario: 진행사항과 Next Action이 모두 비면(공백만 포함) 422이고 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action="  ", next_action=" ")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, ACTION_OR_NEXT_REQUIRED)
    await then_deal_has_no_actions(api, deal["code"])
    await then_history_is(api, deal["code"], [])


async def test_register_next_action_without_due_date_is_rejected(api: Api) -> None:
    """Scenario: Next Action이 있는데 Due Date가 없으면 422이고 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action="", due_date=None)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, DUE_DATE_REQUIRED)
    await then_deal_has_no_actions(api, deal["code"])


async def test_register_due_date_without_next_action_is_rejected(api: Api) -> None:
    """Scenario: Next Action 없이 Due Date만 보내면 422이고 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], next_action="", due_date="2027-01-15")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, DUE_WITHOUT_NEXT)
    await then_deal_has_no_actions(api, deal["code"])


async def test_update_removing_the_next_action_clears_its_status(api: Api) -> None:
    """Scenario: 수정으로 Next Action을 비우면 Due Date·상태·종료 시각이 모두 null이 된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    await given_status_changed(api, created["id"], "done")
    # When
    response = await when_update_action(api, created["id"], next_action="")
    # Then
    then_status_is(response, 200)
    then_body_has(
        response,
        next_action=None,
        due_date=None,
        next_action_status=None,
        next_action_closed_at=None,
    )
    await then_action_status_is(api, created["id"], None)


async def test_update_adding_a_next_action_opens_it(api: Api) -> None:
    """Scenario: 진행사항만 있던 Action에 Next Action을 채우면 Open이 된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_progress_only_action(api, deal["code"])
    # When
    response = await when_update_action(
        api, created["id"], next_action="새 계획", due_date="2027-03-01"
    )
    # Then
    then_status_is(response, 200)
    then_body_has(response, next_action="새 계획", due_date="2027-03-01", next_action_status="open")


async def test_update_adding_progress_to_a_next_only_action_keeps_it_open(api: Api) -> None:
    """Scenario: Next Action만 있던 Action에 진행사항을 채워도 Next Action 상태는 Open이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_next_only_action(api, deal["code"])
    # When
    response = await when_update_action(api, created["id"], action="뒤늦게 적음")
    # Then
    then_status_is(response, 200)
    then_body_has(response, action="뒤늦게 적음", next_action_status="open")


async def test_update_changing_a_closed_next_action_keeps_its_status(api: Api) -> None:
    """Scenario: 종료된 Next Action의 내용·Due를 고쳐도 종료 상태와 종료 시각은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    closed = await given_status_changed(api, created["id"], "not_done", "접음")
    # When
    response = await when_update_action(
        api,
        created["id"],
        next_action="바뀐 계획",
        due_date="2027-05-01",
        memo=closed["memo"],
    )
    # Then
    then_status_is(response, 200)
    then_body_has(
        response,
        next_action="바뀐 계획",
        due_date="2027-05-01",
        next_action_status="not_done",
        next_action_closed_at=closed["next_action_closed_at"],
    )


async def test_update_content_without_touching_next_action_keeps_a_closed_status(
    api: Api,
) -> None:
    """Scenario: 진행사항만 고쳐도 종료 상태는 바뀌지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"])
    closed = await given_status_changed(api, created["id"], "done")
    # When
    response = await when_update_action(api, created["id"], action="진행 수정", memo=closed["memo"])
    # Then
    then_status_is(response, 200)
    then_body_has(response, action="진행 수정", next_action_status="done")


@pytest.mark.parametrize(
    ("overrides", "detail"),
    [
        pytest.param({"action": "", "next_action": ""}, ACTION_OR_NEXT_REQUIRED, id="neither"),
        pytest.param({"due_date": None}, DUE_DATE_REQUIRED, id="next-without-due"),
        pytest.param(
            {"next_action": "", "due_date": "2027-01-15"}, DUE_WITHOUT_NEXT, id="due-without-next"
        ),
    ],
)
async def test_update_with_an_invalid_combination_is_rejected_and_changes_nothing(
    api: Api, overrides: dict[str, object], detail: str
) -> None:
    """Scenario: 입력 규칙을 어기는 수정은 422이고 Action(상태 포함)은 그대로다."""
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
