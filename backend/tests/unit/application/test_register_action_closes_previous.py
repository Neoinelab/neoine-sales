"""RegisterDealAction + close_previous_next_action_id.

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
CREATED_ROW = ("action", "Action", "", f"등록: {SUMMARY}")


async def test_register_closes_the_basis_next_action_as_done(action_env: ActionEnv) -> None:
    """이전 Next Action id와 함께 저장하면 기준 행이 종료(수행)가 된다.

    테스트 코드: AC-036
    """
    # given: KIM이 남긴 Open Next Action 기준 행
    previous = await action_env.act(KIM)

    # when: 그 id를 닫도록 지정해 새 Action을 등록한다
    created = await action_env.act(KIM, close_previous=previous.id, next_action="다음 일정")

    # then: 기준 행은 done이고 종료일이 요청의 업무 날짜(새 Action 등록일)이며 내용은 그대로다
    stored = await action_env.stored(previous.id)
    assert stored.next_action_state == NextActionState(
        NextActionStatus.DONE, closed_on=created.created_at.astimezone().date()
    )
    assert stored.content == previous.content
    assert await action_env.env.uow.deal_comments.count_for_action(previous.id) == 0  # Comment 없음
    # then: 새 Action이 저장되어 Action은 2건이다
    assert (await action_env.stored(created.id)).content.next_action == "다음 일정"
    assert len(action_env.env.uow.deal_actions._items) == 2


async def test_register_closing_a_previous_commits_once(action_env: ActionEnv) -> None:
    """이전 Next Action 종료와 등록은 한 번의 커밋으로 저장된다.

    테스트 코드: AC-036
    """
    # given: 기준 행과 현재 커밋 횟수
    previous = await action_env.act(KIM)
    commits = action_env.env.uow.commits

    # when: 기준 행을 닫으며 등록한다
    await action_env.act(KIM, close_previous=previous.id)

    # then: 커밋은 한 번 늘어난다
    assert action_env.env.uow.commits == commits + 1


async def test_register_can_close_the_previous_even_when_the_new_action_has_no_next_action(
    action_env: ActionEnv,
) -> None:
    """새 Action에 Next Action이 없어도 이전 행을 닫을 수 있다.

    테스트 코드: AC-044
    """
    # given: 기준 행
    previous = await action_env.act(KIM)

    # when: 진행사항만 Action을 등록하며 기준 행을 닫는다
    created = await action_env.act(KIM, close_previous=previous.id, next_action="")

    # then: 새 Action은 상태가 없고 기준 행은 done이다
    assert (await action_env.stored(created.id)).next_action_state is None
    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_register_without_close_id_leaves_previous_open(action_env: ActionEnv) -> None:
    """닫을 id를 보내지 않으면 이전 Next Action은 Open 그대로다.

    테스트 코드: AC-038
    """
    # given: Open 기준 행
    previous = await action_env.act(KIM)

    # when: 닫을 id 없이 등록한다
    await action_env.act(KIM)

    # then: 이전 행은 Open 그대로다
    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()


async def test_register_closes_only_the_basis_and_not_older_next_actions(
    action_env: ActionEnv,
) -> None:
    """기준 행만 닫히고 더 오래된 Next Action은 Open으로 남는다.

    테스트 코드: AC-044
    """
    # given: 오래된 Next Action 행과 기준 행
    older = await action_env.act(KIM)
    basis = await action_env.act(KIM)

    # when: 기준 행 id로 닫으며 등록한다
    await action_env.act(KIM, close_previous=basis.id)

    # then: 오래된 행은 Open이고 기준 행만 done이다
    assert (await action_env.stored(older.id)).next_action_state == NextActionState.open()
    state = (await action_env.stored(basis.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_register_skips_progress_only_rows_when_choosing_the_basis(
    action_env: ActionEnv,
) -> None:
    """진행사항만 있는 최근 행은 건너뛰고 Next Action 행이 기준 행이다.

    테스트 코드: AC-044
    """
    # given: 기준 행과 그 뒤의 진행사항만 Action
    previous = await action_env.act(KIM)
    await action_env.act(KIM, next_action="")  # 더 최근이지만 Next Action이 없는 행

    # when: 기준 행 id로 닫으며 등록한다
    await action_env.act(KIM, close_previous=previous.id)

    # then: 기준 행이 done이다
    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_register_with_stale_close_id_is_conflict_and_saves_nothing(
    action_env: ActionEnv,
) -> None:
    """더 최근 Next Action 행이 생긴 뒤의 id는 409이고 아무것도 저장되지 않는다.

    테스트 코드: AC-039
    """
    # given: 기준 행 뒤에 다른 사람의 Next Action 행이 더 생겼다
    stale = await action_env.act(KIM)
    await action_env.act(PARK)  # 그 사이 더 최근의 Next Action 행이 생겼다
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    # when·then: 옛 기준 행 id로 닫으며 등록하면 충돌 오류다
    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=stale.id)

    # then: Action·이전 행·이력·커밋이 그대로다
    assert len(action_env.env.uow.deal_actions._items) == 2
    assert (await action_env.stored(stale.id)).next_action_state == NextActionState.open()
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits


async def test_register_with_action_id_of_another_deal_is_conflict(action_env: ActionEnv) -> None:
    """다른 Deal의 Action id는 409이고 그 행은 바뀌지 않는다.

    테스트 코드: AC-039
    """
    # given: 다른 Deal의 Action과 이 Deal의 Next Action 행
    other = await action_env.env.new_deal()
    other_code = other.item.deal.id.value
    foreign = await action_env.act(KIM, code=other_code)
    await action_env.act(KIM)  # 이 Deal에도 Next Action 행이 있다

    # when·then: 다른 Deal의 Action id로 닫으며 등록하면 충돌 오류다
    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=foreign.id)

    # then: 다른 Deal의 행은 Open 그대로이고 새 Action은 저장되지 않는다
    assert (await action_env.stored(foreign.id)).next_action_state == NextActionState.open()
    assert len(action_env.env.uow.deal_actions._items) == 2


async def test_register_with_unknown_close_id_is_conflict(action_env: ActionEnv) -> None:
    """없는 Action id는 409다.

    테스트 코드: AC-039
    """
    # given: Next Action 행이 하나 있다
    await action_env.act(KIM)

    # when·then: 없는 id로 닫으며 등록하면 충돌 오류다
    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=DealActionId(new_id()))

    # then: 새 Action은 저장되지 않는다
    assert len(action_env.env.uow.deal_actions._items) == 1


async def test_register_with_close_id_but_no_next_action_in_deal_is_conflict(
    action_env: ActionEnv,
) -> None:
    """Deal에 Next Action이 하나도 없으면 어떤 id도 409다.

    테스트 코드: AC-039
    """
    # given: 진행사항만 Action뿐인 Deal
    progress_only = await action_env.act(KIM, next_action="")

    # when·then: 그 Action id로 닫으며 등록하면 충돌 오류다
    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(KIM, close_previous=progress_only.id)

    # then: 새 Action은 저장되지 않는다
    assert len(action_env.env.uow.deal_actions._items) == 1


async def test_register_skips_an_already_closed_basis(action_env: ActionEnv) -> None:
    """이미 종료된 기준 행은 건너뛰고 새 Action만 저장한다.

    테스트 코드: AC-040
    """
    # given: 미수행으로 닫아 둔 기준 행
    previous = await action_env.act(KIM)
    await action_env.set_status(previous.id, KIM, "not_done", "못 함")
    closed = await action_env.stored(previous.id)
    rows = await action_env.rows()

    # when: 그 id로 닫으며 등록한다
    created = await action_env.act(KIM, close_previous=previous.id)

    # then: 기준 행의 상태·종료 시각·내용·수정 시각이 그대로다
    after = await action_env.stored(previous.id)
    assert after.next_action_state == closed.next_action_state  # not_done과 종료 시각 그대로
    assert after.content == closed.content
    assert after.updated_at == closed.updated_at
    # then: 새 Action만 저장되고 이력은 등록 줄만 늘었다
    assert (await action_env.stored(created.id)).id == created.id
    assert await action_env.rows() == [*rows, CREATED_ROW]  # 상태 변경 이력은 없다


async def test_sales_cannot_close_another_users_next_action(action_env: ActionEnv) -> None:
    """sales는 남의 기준 행을 닫을 수 없다.

    테스트 코드: AC-041
    """
    # given: KIM이 남긴 Open 기준 행
    previous = await action_env.act(KIM)
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    # when·then: 다른 sales가 그 id로 닫으며 등록하면 권한 오류다
    with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
        await action_env.act(PARK, close_previous=previous.id)

    # then: Action·기준 행 상태·이력·커밋이 그대로다
    assert len(action_env.env.uow.deal_actions._items) == 1
    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits


async def test_admin_can_close_anyones_next_action(action_env: ActionEnv) -> None:
    """admin은 남의 기준 행을 닫을 수 있다.

    테스트 코드: AC-041
    """
    # given: KIM이 남긴 Open 기준 행
    previous = await action_env.act(KIM)

    # when: admin이 그 id로 닫으며 등록한다
    await action_env.act(BOSS, close_previous=previous.id)

    # then: 기준 행은 done이다
    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_sales_can_close_their_own_next_action_after_others_acted_on_progress_only(
    action_env: ActionEnv,
) -> None:
    """남의 진행사항만 Action이 뒤에 있어도 본인 기준 행은 닫을 수 있다.

    테스트 코드: AC-041
    """
    # given: KIM의 기준 행과 다른 사람의 진행사항만 Action
    previous = await action_env.act(KIM)
    await action_env.act(PARK, next_action="")  # 다른 사람의 진행사항 전용 행은 기준 행이 아니다

    # when: KIM이 기준 행 id로 닫으며 등록한다
    await action_env.act(KIM, close_previous=previous.id)

    # then: 기준 행은 done이다
    state = (await action_env.stored(previous.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_stale_close_id_is_reported_before_the_permission_check(
    action_env: ActionEnv,
) -> None:
    """409 판정이 권한 403보다 먼저다.

    테스트 코드: AC-042
    """
    # given: KIM의 옛 기준 행과 그 뒤의 KIM의 Next Action 행
    stale = await action_env.act(KIM)
    await action_env.act(KIM)

    # when·then: 다른 sales가 옛 행 id로 닫으며 등록하면 403이 아닌 충돌 오류다
    with raises_with(InvalidStateError, CHANGED):
        await action_env.act(PARK, close_previous=stale.id)


async def test_register_writes_status_history_then_created_history(
    action_env: ActionEnv,
) -> None:
    """종료 줄 다음에 등록 줄이 같은 시각·요청자로 남는다.

    테스트 코드: AC-037
    """
    # given: 기준 행과 등록 전 이력
    previous = await action_env.act(KIM)
    before = await action_env.rows()

    # when: 기준 행을 닫으며 등록한다
    created = await action_env.act(KIM, close_previous=previous.id)

    # then: 이력 끝 두 줄은 종료 줄, 등록 줄 순서다
    assert await action_env.rows() == [*before, CLOSED_ROW, CREATED_ROW]
    # then: 두 줄의 시각은 요청 시각이고 변경자는 요청자다
    entries = await action_env.action_entries()
    closing, registration = entries[-2], entries[-1]
    assert closing.changed_at == registration.changed_at == created.created_at
    assert closing.changed_by == registration.changed_by == KIM.user_id


async def test_admin_closing_records_the_admin_as_the_changer(action_env: ActionEnv) -> None:
    """admin이 닫으면 종료 줄의 변경자가 admin이다.

    테스트 코드: AC-041
    """
    # given: KIM이 남긴 Open 기준 행
    previous = await action_env.act(KIM)

    # when: admin이 기준 행을 닫으며 등록한다
    await action_env.act(BOSS, close_previous=previous.id)

    # then: 종료 줄의 변경자는 admin이다
    entries = await action_env.action_entries()
    assert entries[-2].changed_by == BOSS.user_id


async def test_failed_status_change_keeps_previous_open(action_env: ActionEnv) -> None:
    """동반 변경이 실패하면 이전 Next Action은 Open 그대로다.

    테스트 코드: AC-043
    """
    # given: Open 기준 행과 등록 전 이력
    previous = await action_env.act(KIM)
    rows = await action_env.rows()

    # when·then: 닫으며 매출 없이 계약완료로 바꾸면 거절된다
    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        await action_env.act(
            KIM, close_previous=previous.id, status_changes=(_status("contract_completed"),)
        )

    # then: 기준 행은 Open이고 Action·이력이 그대로다
    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()
    assert len(action_env.env.uow.deal_actions._items) == 1
    assert await action_env.rows() == rows


async def test_invalid_content_keeps_previous_open(action_env: ActionEnv) -> None:
    """내용 오류면 이전 Next Action은 Open 그대로다.

    테스트 코드: AC-043
    """
    # given: Open 기준 행과 등록 전 이력
    previous = await action_env.act(KIM)
    rows = await action_env.rows()

    # when·then: 닫으며 내용이 빈 등록을 하면 내용 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(KIM, close_previous=previous.id, action="", next_action="")

    # then: 기준 행은 Open이고 Action·이력이 그대로다
    assert (await action_env.stored(previous.id)).next_action_state == NextActionState.open()
    assert len(action_env.env.uow.deal_actions._items) == 1
    assert await action_env.rows() == rows


async def test_sales_cannot_close_another_users_already_closed_basis(
    action_env: ActionEnv,
) -> None:
    """이미 종료된 남의 기준 행이어도 권한 판정이 먼저라 403이다."""
    # given: KIM이 남기고 이미 종료(미수행)한 기준 행
    previous = await action_env.act(KIM)
    await action_env.set_status(previous.id, KIM, "not_done", "못 함")
    commits = action_env.env.uow.commits

    # when·then: 다른 sales가 그 id로 닫으며 등록하면 권한 오류다
    with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
        await action_env.act(PARK, close_previous=previous.id)

    # then: Action과 커밋이 그대로다
    assert len(action_env.env.uow.deal_actions._items) == 1
    assert action_env.env.uow.commits == commits
