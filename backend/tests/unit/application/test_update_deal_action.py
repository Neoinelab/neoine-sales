"""UpdateDealAction(AC-10·11, Q4·Q8): 담당자 본인과 admin만, 판정 순서 404 -> 403 -> 422."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.errors import (
    DealActionEditForbiddenError,
    DealActionNotFoundError,
)
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import (
    ACTION_OR_NEXT_REQUIRED,
    BOSS,
    DUE_DATE_REQUIRED,
    DUE_WITHOUT_NEXT,
    EDIT_FORBIDDEN,
    KIM,
    NOT_FOUND,
    PARK,
    SUMMARY_WITH_MEMO,
    VIEWER,
)

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

AFTER = "수정: 제안 · 제안 발표 / Next Action: 견적 회신 (Due 2026-02-01) / Memo: 변경"
CHANGE = {
    "action_type": "제안",
    "action": "제안 발표",
    "next_action": "견적 회신",
    "due_date": date(2026, 2, 1),
    "memo": "변경",
}


async def test_update_action_by_owner_logs_before_and_after(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)

    updated = await action_env.update_as(action.id, KIM, **CHANGE)

    stored = await action_env.stored(action.id)
    assert stored.content.action == "제안 발표"
    assert stored.content.action_type.name == "제안"
    assert stored.updated_at == updated.updated_at == action_env.env.clock.now()
    assert (await action_env.rows())[-1] == ("action", "Action", SUMMARY_WITH_MEMO, AFTER)
    assert (await action_env.action_entries())[-1].changed_by == KIM.user_id


async def test_update_does_not_touch_the_snapshot_actor_acted_at_or_the_deal(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    deal_before = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)

    await action_env.update_as(action.id, KIM, **CHANGE)

    stored = await action_env.stored(action.id)
    assert (stored.actor_user_id, stored.acted_at) == (KIM.user_id, action.acted_at)
    assert stored.snapshot == action.snapshot
    assert stored.created_at == action.created_at
    deal_after = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)
    assert deal_after.updated_at == deal_before.updated_at


async def test_update_action_by_admin_logs_admin_as_changer(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)

    await action_env.update_as(action.id, BOSS, **CHANGE)

    stored = await action_env.stored(action.id)
    assert stored.actor_user_id == KIM.user_id  # 담당자는 그대로
    assert stored.content.action == "제안 발표"
    assert (await action_env.action_entries())[-1].changed_by == BOSS.user_id


async def test_update_action_by_other_sales_is_forbidden_and_changes_nothing(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    with raises_with(DealActionEditForbiddenError, EDIT_FORBIDDEN):
        await action_env.update_as(action.id, PARK, **CHANGE)

    stored = await action_env.stored(action.id)
    assert stored.content == action.content
    assert stored.updated_at == action.updated_at
    assert await action_env.rows() == rows_before


async def test_update_action_by_other_sales_is_forbidden_before_validation(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    with raises_with(DealActionEditForbiddenError, EDIT_FORBIDDEN):
        await action_env.update_as(action.id, PARK, action="   ")


async def test_update_missing_action_is_not_found_before_forbidden(action_env: ActionEnv) -> None:
    missing = DealActionId(new_id())

    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.update_as(missing, PARK, **CHANGE)


async def test_update_action_by_a_read_only_user_is_forbidden_even_for_own_id(
    action_env: ActionEnv,
) -> None:
    own = make_deal_action(deal_code=action_env.deal.item.deal.id, actor_user_id=VIEWER.user_id)
    await action_env.env.uow.deal_actions.add(own)

    with pytest.raises(DealActionEditForbiddenError):
        await action_env.update_as(own.id, VIEWER, **CHANGE)


async def test_update_action_by_owner_with_blank_progress_is_a_validation_error(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.update_as(action.id, KIM, action="  ", next_action="", due_date=None)

    assert (await action_env.stored(action.id)).content == action.content


async def test_update_action_without_due_date_is_a_validation_error(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    with raises_with(InvalidValueError, DUE_DATE_REQUIRED):
        await action_env.update_as(action.id, KIM, due_date=None)


async def test_update_action_without_change_logs_nothing(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    result = await action_env.update_as(action.id, KIM)  # 같은 내용

    assert await action_env.rows() == rows_before
    assert (await action_env.stored(action.id)).updated_at == action.updated_at
    assert result.updated_at == action.updated_at


async def test_update_action_with_content_equal_after_trim_logs_nothing(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    await action_env.update_as(action.id, KIM, action="  킥오프 미팅  ", memo=" 요구사항 정리 ")

    assert await action_env.rows() == rows_before
    assert (await action_env.stored(action.id)).updated_at == action.updated_at


async def test_update_action_saves_long_text_in_full_and_clips_only_the_history(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    await action_env.update_as(action.id, KIM, action="가" * 5_000, memo="메" * 20_000)

    stored = await action_env.stored(action.id)
    assert stored.content.action is not None
    assert (len(stored.content.action), len(stored.content.memo)) == (5_000, 20_000)
    (_, _, _, after) = (await action_env.rows())[-1]
    assert len(after) == 1_000
    assert after.endswith("…")


async def test_a_change_visible_only_after_the_history_limit_still_logs_one_entry(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM, action="가" * 2_000)
    entries_before = len(await action_env.action_entries())

    await action_env.update_as(action.id, KIM, action="가" * 1_999 + "나")

    assert len(await action_env.action_entries()) == entries_before + 1
    stored_progress = (await action_env.stored(action.id)).content.action
    assert stored_progress is not None
    assert stored_progress.endswith("나")


async def test_update_clears_next_action(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)

    await action_env.update_as(action.id, KIM, next_action="", due_date=None)

    stored = await action_env.stored(action.id)
    assert stored.content.next_action is None
    assert stored.content.due_date is None
    assert stored.next_action_state is None
    assert (await action_env.rows())[-1][3] == "수정: 미팅 · 킥오프 미팅 / Memo: 요구사항 정리"


async def test_update_clearing_next_action_of_a_closed_one_removes_status_and_time(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done")

    await action_env.update_as(action.id, KIM, next_action="", due_date=None)

    assert (await action_env.stored(action.id)).next_action_state is None


async def test_update_adding_next_action_to_a_progress_only_action_opens_it(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM, next_action="")

    await action_env.update_as(action.id, KIM, next_action="새 계획", due_date=date(2026, 3, 1))

    assert (await action_env.stored(action.id)).next_action_state == NextActionState.open()


async def test_update_next_action_text_of_a_closed_one_keeps_status_and_time(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    closed = await action_env.set_status(action.id, KIM, "not_done", "접음")

    await action_env.update_as(
        action.id, KIM, next_action="바뀐 계획", due_date=date(2026, 5, 1), memo=closed.content.memo
    )

    stored = await action_env.stored(action.id)
    assert stored.content.next_action == "바뀐 계획"
    assert stored.next_action_state == closed.next_action_state
    assert stored.next_action_state is not None
    assert stored.next_action_state.status is NextActionStatus.NOT_DONE


async def test_update_to_progress_only_content_is_accepted(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)

    updated = await action_env.update_as(action.id, KIM, action="진행만", next_action="")

    assert updated.content.action == "진행만"
    assert updated.content.next_action is None


async def test_update_due_date_without_next_action_is_a_validation_error(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    with raises_with(InvalidValueError, DUE_WITHOUT_NEXT):
        await action_env.update_as(action.id, KIM, next_action="", due_date=date(2026, 2, 1))

    assert (await action_env.stored(action.id)).content == action.content
