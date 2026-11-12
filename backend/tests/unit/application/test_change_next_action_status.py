"""ChangeNextActionStatus: 작성자·admin만, 404 -> 403 -> 422/409 순서, History 한 건."""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal_action.errors import DealActionNotFoundError, DealActionStatusForbiddenError
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import BOSS, KIM, NOT_FOUND, PARK, VIEWER

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

STATUS_FORBIDDEN = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."
NO_NEXT_ACTION = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."
OPEN_WITH_MEMO = "Open으로 되돌릴 때는 메모를 남길 수 없습니다."
NUL_MEMO = "메모에는 NUL 문자를 쓸 수 없습니다"
DUE = "(Due 2026-01-15)"


async def test_actor_closes_and_history_written(action_env: ActionEnv) -> None:
    """작성자가 메모와 함께 종료(수행)하면 상태·종료 시각·Memo가 바뀌고 History 1건이 남는다.

    테스트 코드: NA-001
    """
    # given: sales kim이 등록한 Open Action(Memo "기존")
    action = await action_env.act(KIM, memo="기존")
    commits = action_env.env.uow.commits
    before_rows = await action_env.rows()
    # when: kim이 상태를 done, 메모 "전달 완료"로 바꾼다
    changed = await action_env.set_status(action.id, KIM, "done", "전달 완료")
    # then: 상태 done, 종료 시각은 요청 시각, Memo는 "기존\n전달 완료"이고 응답도 같다
    stored = await action_env.stored(action.id)
    assert changed.id == action.id
    assert stored.next_action_state == NextActionState(
        status=NextActionStatus.DONE, closed_at=action_env.env.clock.now()
    )
    assert changed.next_action_state == stored.next_action_state
    assert stored.content.memo == "기존\n전달 완료"
    assert changed.content.memo == "기존\n전달 완료"
    assert action_env.env.uow.commits == commits + 1
    # then: History에 정해진 문구의 1건이 늘고 변경자·변경 시각은 요청자·요청 시각이다
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
    """admin은 다른 사람의 Action을 종료(미수행)할 수 있고 History 변경자는 admin이다.

    테스트 코드: NA-012
    """
    # given: sales kim의 Open Action
    action = await action_env.act(KIM)
    # when: admin이 not_done으로 바꾼다
    await action_env.set_status(action.id, BOSS, "not_done")
    # then: 상태가 not_done이 되고 새 History 항목의 변경자는 admin이다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state is not None
    assert stored.next_action_state.status is NextActionStatus.NOT_DONE
    assert (await action_env.action_entries())[-1].changed_by == BOSS.user_id


@pytest.mark.parametrize("memo", ["", "   \n "])
async def test_closing_without_a_memo_keeps_the_memo(action_env: ActionEnv, memo: str) -> None:
    """비었거나 공백뿐인 종료 메모는 Memo를 바꾸지 않고 종료만 한다.

    테스트 코드: NA-003
    """
    # given: Memo "요구사항 정리"인 Open Action
    action = await action_env.act(KIM, memo="요구사항 정리")
    # when: 작성자가 not_done으로 바꾸며 빈 메모 또는 공백뿐인 메모를 보낸다
    await action_env.set_status(action.id, KIM, "not_done", memo)
    # then: 상태는 not_done, 종료 시각이 있고 Memo는 그대로이며 이력 변경 후 값에 Memo가 없다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState(
        status=NextActionStatus.NOT_DONE, closed_at=action_env.env.clock.now()
    )
    assert stored.content.memo == "요구사항 정리"
    assert (await action_env.rows())[-1][3] == "종료(미수행)"


async def test_reopening_clears_closed_time_and_logs_the_change(action_env: ActionEnv) -> None:
    """Open으로 되돌리면 종료 시각이 없어지고 덧붙인 Memo는 남으며 History가 한 건 남는다.

    테스트 코드: NA-005, NA-017
    """
    # given: 메모 "끝"을 붙여 종료(수행)한 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done", "끝")
    # when: 작성자가 open으로 바꾼다
    await action_env.set_status(action.id, KIM, "open")
    # then: 상태는 open, 종료 시각은 null, Memo는 "…\n끝" 그대로이고 이력은 종료(수행) -> Open이다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert stored.content.memo.endswith("\n끝")
    assert (await action_env.rows())[-1][2:] == (f"요구사항 문서 전달 {DUE} · 종료(수행)", "Open")


async def test_each_status_change_logs_one_entry_with_the_fixed_wording(
    action_env: ActionEnv,
) -> None:
    """세 번 바꾸면(done+메모, open, not_done) History가 세 건 차례로 늘고 문구가 정해진 형식이다.

    테스트 코드: NA-017
    """
    # given: Next Action "요구사항 문서 전달", Due 2026-01-15인 Open Action
    action = await action_env.act(KIM)
    base = len(await action_env.action_entries())
    # when: 작성자가 차례로 done+메모 "전달 완료", open, not_done(메모 없음)으로 바꾼다
    await action_env.set_status(action.id, KIM, "done", "전달 완료")
    await action_env.set_status(action.id, KIM, "open")
    await action_env.set_status(action.id, KIM, "not_done")
    # then: 구분 action·대상 Next Action, 변경 전/후가 정해진 문구이고 변경자는 요청자다
    entries = (await action_env.action_entries())[base:]
    assert [
        (e.draft.category.value, e.draft.target, e.draft.before, e.draft.after) for e in entries
    ] == [
        (
            "action",
            "Next Action",
            f"요구사항 문서 전달 {DUE} · Open",
            "종료(수행) / Memo: 전달 완료",
        ),
        ("action", "Next Action", f"요구사항 문서 전달 {DUE} · 종료(수행)", "Open"),
        ("action", "Next Action", f"요구사항 문서 전달 {DUE} · Open", "종료(미수행)"),
    ]
    assert {e.changed_by for e in entries} == {KIM.user_id}


async def test_a_long_closing_memo_is_clipped_in_history_but_kept_in_memo(
    action_env: ActionEnv,
) -> None:
    """1,000자를 넘는 종료 메모는 이력 값만 잘리고 Memo에는 전체가 붙는다.

    테스트 코드: NA-018
    """
    # given: Memo "기존"인 Open Action
    action = await action_env.act(KIM, memo="기존")
    # when: 작성자가 1,500자 메모로 종료(수행)한다
    await action_env.set_status(action.id, KIM, "done", "가" * 1_500)
    # then: 이력 변경 후 값은 999자 + "…"이고 Memo에는 메모 전체가 붙는다
    after = (await action_env.rows())[-1][3]
    assert len(after) == 1_000
    assert after.startswith("종료(수행) / Memo: ")
    assert after.endswith("…")
    assert (await action_env.stored(action.id)).content.memo == "기존\n" + "가" * 1_500


async def test_status_change_does_not_change_other_content_or_the_deal(
    action_env: ActionEnv,
) -> None:
    """상태 변경은 진행사항·Next Action·Due·유형·수행 정보·스냅숏과 Deal 수정 시각을 바꾸지 않는다.

    테스트 코드: NA-011
    """
    # given: kim의 Open Action과 그 Deal의 수정 시각
    action = await action_env.act(KIM)
    deal_updated = (await action_env.env.uow.deals.get(action_env.deal.item.deal.id)).updated_at
    # when: kim이 done으로 바꾼다
    await action_env.set_status(action.id, KIM, "done")
    # then: 내용·수행 일시·작성자·스냅숏은 등록 때와 같고 Deal 수정 시각은 그대로다
    stored = await action_env.stored(action.id)
    assert stored.content == action.content
    assert stored.acted_at == action.acted_at
    assert stored.actor_user_id == action.actor_user_id
    assert stored.snapshot == action.snapshot
    deal = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)
    assert deal.updated_at == deal_updated


async def test_other_sales_forbidden_without_change(action_env: ActionEnv) -> None:
    """작성자가 아닌 sales는 403 고정 문구이고 Action·History·커밋이 그대로다.

    테스트 코드: NA-013
    """
    # given: sales kim의 Open Action
    action = await action_env.act(KIM)
    rows = await action_env.rows()
    commits = action_env.env.uow.commits
    # when·then: sales park이 done, 메모 "남의 것"으로 바꾸면 403 고정 문구다
    with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
        await action_env.set_status(action.id, PARK, "done", "남의 것")
    # then: 상태·Memo·History·커밋이 그대로다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert stored.content == action.content
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits


async def test_read_only_user_is_forbidden_even_for_own_id(action_env: ActionEnv) -> None:
    """user 역할은 자기가 작성자로 기록된 Action이어도 상태를 바꿀 수 없다.

    테스트 코드: NA-014
    """
    # given: 작성자 id가 user 역할 사용자 자신인 Action
    own = make_deal_action(deal_code=action_env.deal.item.deal.id, actor_user_id=VIEWER.user_id)
    await action_env.env.uow.deal_actions.add(own)
    # when·then: 그 user가 done으로 바꾸면 403이다(HTTP에서는 쓰기 가드가 먼저 막는다)
    with pytest.raises(DealActionStatusForbiddenError):
        await action_env.set_status(own.id, VIEWER, "done")
    # then: 상태가 그대로다
    assert (await action_env.stored(own.id)).next_action_state == NextActionState.open()


async def test_missing_action_not_found_before_forbidden(action_env: ActionEnv) -> None:
    """없는 Action은 작성자 확인보다 먼저 404다.

    테스트 코드: NA-015
    """
    # when·then: 어떤 Action에도 없는 id로 user 역할 행위자가 done을 요청하면 403이 아니라 404다
    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.set_status(DealActionId(new_id()), VIEWER, "done")


async def test_same_status_conflicts_without_change(action_env: ActionEnv) -> None:
    """Open Action을 open으로 바꾸면 409이고 Memo·History가 그대로다.

    테스트 코드: NA-007
    """
    # given: Open Action
    action = await action_env.act(KIM)
    rows = await action_env.rows()
    # when·then: 작성자가 open으로 바꾸면 409 "이미 Open 상태입니다."다
    with raises_with(InvalidStateError, "이미 Open 상태입니다."):
        await action_env.set_status(action.id, KIM, "open")
    # then: History와 내용이 그대로다
    assert await action_env.rows() == rows
    assert (await action_env.stored(action.id)).content == action.content


async def test_same_closed_status_conflicts_without_change(action_env: ActionEnv) -> None:
    """종료(수행) Action을 메모와 함께 done으로 바꾸면 409이고 Memo·종료 시각·History가 그대로다.

    테스트 코드: NA-007
    """
    # given: 메모 "첫 종료"로 종료(수행)된 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done", "첫 종료")
    closed = (await action_env.stored(action.id)).next_action_state
    rows = await action_env.rows()
    # when·then: 작성자가 done, 메모 "또 종료"로 바꾸면 409 "이미 종료(수행) 상태입니다."다
    with raises_with(InvalidStateError, "이미 종료(수행) 상태입니다."):
        await action_env.set_status(action.id, KIM, "done", "또 종료")
    # then: Memo·종료 시각·History 건수가 그대로다
    stored = await action_env.stored(action.id)
    assert stored.content.memo.endswith("\n첫 종료")
    assert "또 종료" not in stored.content.memo
    assert stored.next_action_state == closed
    assert await action_env.rows() == rows


async def test_action_without_next_action_conflicts_without_change(
    action_env: ActionEnv,
) -> None:
    """Next Action이 없는 Action의 상태를 바꾸면 409이고 Memo·History가 그대로다.

    테스트 코드: NA-008
    """
    # given: 진행사항만 Action
    action = await action_env.act(KIM, next_action="")
    rows = await action_env.rows()
    # when·then: 작성자가 done, 메모 "메모"로 바꾸면 409다
    with raises_with(InvalidStateError, NO_NEXT_ACTION):
        await action_env.set_status(action.id, KIM, "done", "메모")
    # then: 내용과 History가 그대로다
    assert (await action_env.stored(action.id)).content == action.content
    assert await action_env.rows() == rows


async def test_open_with_memo_is_a_validation_error(action_env: ActionEnv) -> None:
    """Open으로 되돌리며 메모를 보내면 422이고 상태·종료 시각·Memo·History가 그대로다.

    테스트 코드: NA-006
    """
    # given: 종료(수행)된 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done")
    before = await action_env.stored(action.id)
    rows = await action_env.rows()
    # when·then: 작성자가 open, 메모 "되돌리며 메모"로 바꾸면 422 문구다
    with raises_with(InvalidValueError, OPEN_WITH_MEMO):
        await action_env.set_status(action.id, KIM, "open", "되돌리며 메모")
    # then: 상태·종료 시각·Memo·History가 그대로다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == before.next_action_state
    assert stored.content.memo == before.content.memo
    assert await action_env.rows() == rows


async def test_open_with_a_blank_memo_is_allowed(action_env: ActionEnv) -> None:
    """Open으로 되돌릴 때 공백뿐인 메모는 허용된다.

    테스트 코드: NA-006
    """
    # given: 종료(수행)된 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done")
    # when: 작성자가 open, 메모 "   "로 바꾼다
    await action_env.set_status(action.id, KIM, "open", "   ")
    # then: Open이 된다
    assert (await action_env.stored(action.id)).next_action_state == NextActionState.open()


async def test_closing_memo_with_nul_is_rejected_without_change(action_env: ActionEnv) -> None:
    """종료 메모에 NUL 문자가 있으면 422 invalid-value이고 Action·History가 그대로다.

    테스트 코드: NA-009
    """
    # given: Open Action
    action = await action_env.act(KIM)
    rows = await action_env.rows()
    # when·then: 작성자가 done, 메모 "가\x00나"로 바꾸면 422 NUL 문구다
    with raises_with(InvalidValueError, NUL_MEMO):
        await action_env.set_status(action.id, KIM, "done", "가\x00나")
    # then: 상태·Memo·History가 그대로다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert stored.content == action.content
    assert await action_env.rows() == rows


async def test_failed_change_writes_no_history(action_env: ActionEnv) -> None:
    """거절된 변경(같은 상태·작성자 아님)은 History를 남기지 않는다.

    테스트 코드: NA-007, NA-013
    """
    # given: Open Action과 현재 Action History 건수
    action = await action_env.act(KIM)
    before = len(await action_env.action_entries())
    # when·then: 같은 상태로 바꾸면 409, 다른 sales가 바꾸면 403이다
    with pytest.raises(InvalidStateError):
        await action_env.set_status(action.id, KIM, "open")
    with pytest.raises(DealActionStatusForbiddenError):
        await action_env.set_status(action.id, PARK, "done")
    # then: History 건수가 그대로다
    assert len(await action_env.action_entries()) == before
