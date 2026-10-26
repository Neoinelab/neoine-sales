"""RegisterDealAction + close_previous_next_action_id(R4, AC4-1~4-7).

새 Action을 저장하면서 같은 트랜잭션에서 이전 Next Action(= 그 Deal에서 Next Action이 있는 가장
최근 Action)을 종료(수행)로 바꾼다. 어떤 이유로든 저장이 실패하면 이전 행도 바뀌지 않는다.
"""

from typing import TYPE_CHECKING

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal_action.errors import DealActionStatusForbiddenError
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import (
    ACTION_OR_NEXT_REQUIRED,
    BOSS,
    KIM,
    PARK,
    SUMMARY,
)
from tests.unit.application.apply_helpers import REVENUE_REQUIRED

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv


def _status(value: str) -> StatusChangeInput:
    return StatusChangeInput(field="status_key", value=value)


CHANGED = "이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요."
STATUS_FORBIDDEN = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."
DUE = "(Due 2026-01-15)"
CLOSED_ROW = ("action", "Next Action", f"요구사항 문서 전달 {DUE} · Open", "종료(수행)")
CREATED_ROW = ("action", "Action", "", f"등록: {SUMMARY} / Memo: 요구사항 정리")


async def test_register_closes_the_basis_next_action_as_done(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM, memo="기존 메모")

    created = await action_env.act(KIM, close_previous=previous.id, next_action="다음 일정")

    stored = await action_env.stored(previous.id)
    assert stored.next_action_state == NextActionState.of(NextActionStatus.DONE, created.acted_at)
    assert stored.content.memo == "기존 메모"  # 종료 메모는 없다
    assert (await action_env.stored(created.id)).content.next_action == "다음 일정"
    assert len(action_env.env.uow.deal_actions._items) == 2


async def test_register_closing_a_previous_commits_once(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)
    commits = action_env.env.uow.commits

    await action_env.act(KIM, close_previous=previous.id)

    assert action_env.env.uow.commits == commits + 1


async def test_register_can_close_the_previous_even_when_the_new_action_has_no_next_action(
    action_env: ActionEnv,
) -> None:
    previous = await action_env.act(KIM)

    created = await action_env.act(KIM, close_previous=previous.id, next_action="")

    assert (await action_env.stored(created.id)).next_action_state is None
    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_register_without_close_id_leaves_previous_open(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)

    await action_env.act(KIM)

    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()


async def test_register_closes_only_the_basis_and_not_older_next_actions(
    action_env: ActionEnv,
) -> None:
    older = await action_env.act(KIM)
    basis = await action_env.act(KIM)

    await action_env.act(KIM, close_previous=basis.id)

    assert (await action_env.stored(older.id)).next_action_state == NextActionState.open()
    state = (await action_env.stored(basis.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_register_skips_progress_only_rows_when_choosing_the_basis(
    action_env: ActionEnv,
) -> None:
    previous = await action_env.act(KIM)
    await action_env.act(KIM, next_action="")  # 더 최근이지만 Next Action이 없는 행

    await action_env.act(KIM, close_previous=previous.id)

    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_register_with_stale_close_id_is_conflict_and_saves_nothing(
    action_env: ActionEnv,
) -> None:
    stale = await action_env.act(KIM)
    await action_env.act(PARK)  # 그 사이 더 최근의 Next Action 행이 생겼다
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=stale.id)

    assert len(action_env.env.uow.deal_actions._items) == 2
    assert (await action_env.stored(stale.id)).next_action_state == NextActionState.open()
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits


async def test_register_with_action_id_of_another_deal_is_conflict(action_env: ActionEnv) -> None:
    other = await action_env.env.new_deal()
    other_code = other.item.deal.id.value
    foreign = await action_env.act(KIM, code=other_code)
    await action_env.act(KIM)  # 이 Deal에도 Next Action 행이 있다

    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=foreign.id)

    assert (await action_env.stored(foreign.id)).next_action_state == NextActionState.open()
    assert len(action_env.env.uow.deal_actions._items) == 2


async def test_register_with_unknown_close_id_is_conflict(action_env: ActionEnv) -> None:
    await action_env.act(KIM)

    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=DealActionId(new_id()))

    assert len(action_env.env.uow.deal_actions._items) == 1


async def test_register_with_close_id_but_no_next_action_in_deal_is_conflict(
    action_env: ActionEnv,
) -> None:
    progress_only = await action_env.act(KIM, next_action="")

    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=progress_only.id)

    assert len(action_env.env.uow.deal_actions._items) == 1


async def test_register_skips_an_already_closed_basis(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)
    await action_env.set_status(previous.id, KIM, "not_done", "못 함")
    closed = await action_env.stored(previous.id)
    rows = await action_env.rows()

    created = await action_env.act(KIM, close_previous=previous.id)

    after = await action_env.stored(previous.id)
    assert after.next_action_state == closed.next_action_state  # not_done과 종료 시각 그대로
    assert after.content == closed.content
    assert after.updated_at == closed.updated_at
    assert (await action_env.stored(created.id)).id == created.id
    assert await action_env.rows() == [*rows, CREATED_ROW]  # 상태 변경 이력은 없다


async def test_sales_cannot_close_another_users_next_action(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
        await action_env.act(PARK, close_previous=previous.id)

    assert len(action_env.env.uow.deal_actions._items) == 1
    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits


async def test_admin_can_close_anyones_next_action(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)

    await action_env.act(BOSS, close_previous=previous.id)

    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_sales_can_close_their_own_next_action_after_others_acted_on_progress_only(
    action_env: ActionEnv,
) -> None:
    previous = await action_env.act(KIM)
    await action_env.act(PARK, next_action="")  # 다른 사람의 진행사항 전용 행은 기준 행이 아니다

    await action_env.act(KIM, close_previous=previous.id)

    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_stale_close_id_is_reported_before_the_permission_check(
    action_env: ActionEnv,
) -> None:
    stale = await action_env.act(KIM)
    await action_env.act(KIM)

    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(PARK, close_previous=stale.id)


async def test_register_writes_status_history_then_created_history(
    action_env: ActionEnv,
) -> None:
    previous = await action_env.act(KIM)
    before = await action_env.rows()

    created = await action_env.act(KIM, close_previous=previous.id)

    assert await action_env.rows() == [*before, CLOSED_ROW, CREATED_ROW]
    entries = await action_env.action_entries()
    closing, registration = entries[-2], entries[-1]
    assert closing.changed_at == registration.changed_at == created.acted_at
    assert closing.changed_by == registration.changed_by == KIM.user_id


async def test_admin_closing_records_the_admin_as_the_changer(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)

    await action_env.act(BOSS, close_previous=previous.id)

    entries = await action_env.action_entries()
    assert entries[-2].changed_by == BOSS.user_id


async def test_failed_status_change_keeps_previous_open(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)
    rows = await action_env.rows()

    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        await action_env.act(
            KIM, close_previous=previous.id, status_changes=(_status("contract_completed"),)
        )

    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()
    assert len(action_env.env.uow.deal_actions._items) == 1
    assert await action_env.rows() == rows


async def test_invalid_content_keeps_previous_open(action_env: ActionEnv) -> None:
    previous = await action_env.act(KIM)
    rows = await action_env.rows()

    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(KIM, close_previous=previous.id, action="", next_action="")

    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()
    assert len(action_env.env.uow.deal_actions._items) == 1
    assert await action_env.rows() == rows
