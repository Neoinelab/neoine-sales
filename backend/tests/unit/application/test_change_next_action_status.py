"""ChangeNextActionStatus(AC-8~13): 작성자·admin만, 404 -> 403 -> 422/409 순서, History 한 건."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal_action.errors import DealActionNotFoundError, DealActionStatusForbiddenError
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.expect import raises_with
from tests.unit.application.action_env import BOSS, KIM, NOT_FOUND, PARK, VIEWER

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

STATUS_FORBIDDEN = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."
NO_NEXT_ACTION = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."
DUE = "(Due 2026-01-15)"


async def test_actor_closes_and_history_written(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, memo="기존")
    commits = action_env.env.uow.commits
    before_rows = await action_env.rows()

    changed = await action_env.set_status(action.id, KIM, "done", "전달 완료")

    stored = await action_env.stored(action.id)
    assert changed.id == action.id
    assert stored.next_action_state == NextActionState(
        status=NextActionStatus.DONE, closed_at=action_env.env.clock.now()
    )
    assert stored.content.memo == "기존\n전달 완료"
    assert action_env.env.uow.commits == commits + 1
    rows = await action_env.rows()
    assert rows[:-1] == before_rows
    assert rows[-1] == (
        "action",
        "Next Action",
        f"요구사항 문서 전달 {DUE} · Open",
        "종료(수행) / Memo: 전달 완료",
    )
    entry = (await action_env.action_entries())[-1]
    assert entry.changed_by == KIM.user_id
    assert entry.changed_at == action_env.env.clock.now()


async def test_admin_closes_others_action(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)

    await action_env.set_status(action.id, BOSS, "not_done")

    stored = await action_env.stored(action.id)
    assert stored.next_action_state is not None
    assert stored.next_action_state.status is NextActionStatus.NOT_DONE
    assert (await action_env.action_entries())[-1].changed_by == BOSS.user_id


async def test_reopening_clears_closed_time_and_logs_the_change(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done", "끝")

    await action_env.set_status(action.id, KIM, "open")

    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert stored.content.memo.endswith("\n끝")
    assert (await action_env.rows())[-1][2:] == (f"요구사항 문서 전달 {DUE} · 종료(수행)", "Open")


async def test_status_change_does_not_change_the_acted_time_or_deal(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    deal_updated = (await action_env.env.uow.deals.get(action_env.deal.item.deal.id)).updated_at

    await action_env.set_status(action.id, KIM, "done")

    stored = await action_env.stored(action.id)
    assert stored.acted_at == action.acted_at
    deal = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)
    assert deal.updated_at == deal_updated


async def test_other_sales_forbidden_without_change(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
        await action_env.set_status(action.id, PARK, "done", "남의 것")

    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert stored.content == action.content
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits


async def test_read_only_user_is_forbidden_even_for_own_id(action_env: ActionEnv) -> None:
    own = make_deal_action(deal_code=action_env.deal.item.deal.id, actor_user_id=VIEWER.user_id)
    await action_env.env.uow.deal_actions.add(own)

    with pytest.raises(DealActionStatusForbiddenError):
        await action_env.set_status(own.id, VIEWER, "done")


async def test_missing_action_not_found_before_forbidden(action_env: ActionEnv) -> None:
    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.set_status(DealActionId(uuid4()), VIEWER, "done")


async def test_same_status_conflicts_without_change(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    rows = await action_env.rows()

    with raises_with(InvalidStateError, "이미 Open 상태입니다."):
        await action_env.set_status(action.id, KIM, "open")

    assert await action_env.rows() == rows
    assert (await action_env.stored(action.id)).content == action.content


async def test_action_without_next_action_conflicts_without_change(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM, next_action="")
    rows = await action_env.rows()

    with raises_with(InvalidStateError, NO_NEXT_ACTION):
        await action_env.set_status(action.id, KIM, "done", "메모")

    assert (await action_env.stored(action.id)).content == action.content
    assert await action_env.rows() == rows


async def test_open_with_memo_is_a_validation_error(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done")
    rows = await action_env.rows()

    with pytest.raises(InvalidValueError):
        await action_env.set_status(action.id, KIM, "open", "되돌리며 메모")

    assert await action_env.rows() == rows


async def test_failed_change_writes_no_history(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    before = len(await action_env.action_entries())

    with pytest.raises(InvalidStateError):
        await action_env.set_status(action.id, KIM, "open")
    with pytest.raises(DealActionStatusForbiddenError):
        await action_env.set_status(action.id, PARK, "done")

    assert len(await action_env.action_entries()) == before
