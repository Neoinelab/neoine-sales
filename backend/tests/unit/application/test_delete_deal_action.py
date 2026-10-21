"""DeleteDealAction(AC-12, Q8): 담당자 본인과 admin만, 물리 삭제와 이력, 판정 순서 404 -> 403."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import NextActionSummary
from app.domain.deal_action.errors import (
    DealActionDeleteForbiddenError,
    DealActionNotFoundError,
)
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import (
    BOSS,
    DELETE_FORBIDDEN,
    KIM,
    NOT_FOUND,
    PARK,
    SUMMARY_WITH_MEMO,
    VIEWER,
)

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv


async def test_delete_action_by_owner_logs_history_and_removes_the_row(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    await action_env.delete.execute(action.id, KIM)

    with pytest.raises(DealActionNotFoundError):
        await action_env.stored(action.id)
    assert (await action_env.rows())[-1] == ("action", "Action", SUMMARY_WITH_MEMO, "삭제")
    assert (await action_env.action_entries())[-1].changed_by == KIM.user_id


async def test_delete_action_by_owner_logs_history_and_next_action_falls_back(
    action_env: ActionEnv,
) -> None:
    await action_env.act(KIM, next_action="먼저 할 일", due_date=date(2026, 3, 1))
    latest = await action_env.act(KIM, next_action="나중 할 일", due_date=date(2026, 4, 1))

    await action_env.delete.execute(latest.id, KIM)

    detail = await action_env.env.get.execute(action_env.code)
    assert detail.item.next_action == NextActionSummary(
        "먼저 할 일", date(2026, 3, 1), NextActionStatus.OPEN
    )


async def test_deleting_the_only_action_leaves_the_deal_without_a_next_action(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    await action_env.delete.execute(action.id, KIM)

    assert (await action_env.env.get.execute(action_env.code)).item.next_action is None


async def test_delete_action_by_admin_removes_another_users_action(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)

    await action_env.delete.execute(action.id, BOSS)

    with pytest.raises(DealActionNotFoundError):
        await action_env.stored(action.id)
    assert (await action_env.action_entries())[-1].changed_by == BOSS.user_id


async def test_delete_action_by_other_sales_is_forbidden_and_keeps_action(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    with raises_with(DealActionDeleteForbiddenError, DELETE_FORBIDDEN):
        await action_env.delete.execute(action.id, PARK)

    assert (await action_env.stored(action.id)).content == action.content
    assert await action_env.rows() == rows_before


async def test_delete_action_by_a_read_only_user_is_forbidden_even_for_own_id(
    action_env: ActionEnv,
) -> None:
    own = make_deal_action(deal_code=action_env.deal.item.deal.id, actor_user_id=VIEWER.user_id)
    await action_env.env.uow.deal_actions.add(own)

    with pytest.raises(DealActionDeleteForbiddenError):
        await action_env.delete.execute(own.id, VIEWER)

    assert (await action_env.stored(own.id)).id == own.id


async def test_delete_missing_action_is_not_found_whoever_asks(action_env: ActionEnv) -> None:
    missing = DealActionId(new_id())

    for actor in (KIM, PARK, BOSS):
        with raises_with(DealActionNotFoundError, NOT_FOUND):
            await action_env.delete.execute(missing, actor)


async def test_deleting_the_action_twice_is_not_found_the_second_time(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    await action_env.delete.execute(action.id, KIM)

    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.delete.execute(action.id, KIM)


async def test_delete_clips_the_history_summary_but_the_row_is_removed(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM, action="가" * 3_000)

    await action_env.delete.execute(action.id, KIM)

    (_, _, before, after) = (await action_env.rows())[-1]
    assert (len(before), after) == (1_000, "삭제")
    assert before.endswith("…")
