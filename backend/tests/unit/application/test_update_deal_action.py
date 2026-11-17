"""UpdateDealAction: 담당자 본인과 admin만, 판정 순서 404 -> 403 -> 422."""

from datetime import date
from typing import TYPE_CHECKING, Any

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
    SUMMARY,
    VIEWER,
)

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

AFTER = "수정: 제안 · 제안 발표 / Next Action: 견적 회신 (Due 2026-02-01)"
CHANGE: dict[str, Any] = {
    "action_type": "제안",
    "action": "제안 발표",
    "next_action": "견적 회신",
    "due_date": date(2026, 2, 1),
}


async def test_update_action_by_owner_logs_before_and_after(action_env: ActionEnv) -> None:
    """담당자가 고치면 내용이 바뀌고 수정 전후 이력 1건이 남는다.

    테스트 코드: AC-046
    """
    # given: KIM이 남긴 기본 Action
    action = await action_env.act(KIM)

    # when: KIM이 유형·진행사항·Next Action·Due를 모두 고친다
    updated = await action_env.update_as(action.id, KIM, **CHANGE)

    # then: 내용과 수정 시각이 바뀐다
    stored = await action_env.stored(action.id)
    assert stored.content.action == "제안 발표"
    assert stored.content.action_type.name == "제안"
    assert stored.updated_at == updated.updated_at == action_env.env.clock.now()
    # then: 이력 최신 줄은 수정 전 요약과 "수정: …"이고 변경자는 KIM이다
    assert (await action_env.rows())[-1] == ("action", "Action", SUMMARY, AFTER)
    assert (await action_env.action_entries())[-1].changed_by == KIM.user_id


async def test_update_does_not_touch_the_snapshot_actor_acted_on_or_the_deal(
    action_env: ActionEnv,
) -> None:
    """수정해도 수행일·담당자·스냅숏·Deal은 바뀌지 않는다.

    테스트 코드: AC-046, AC-035
    """
    # given: KIM이 남긴 Action과 Deal의 수정 시각
    action = await action_env.act(KIM)
    deal_before = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)

    # when: KIM이 내용을 고친다
    await action_env.update_as(action.id, KIM, **CHANGE)

    # then: 담당자·수행일·스냅숏·등록 시각이 그대로다
    stored = await action_env.stored(action.id)
    assert (stored.actor_user_id, stored.acted_on) == (KIM.user_id, action.acted_on)
    assert stored.snapshot == action.snapshot
    assert stored.created_at == action.created_at
    # then: Deal 수정 시각이 그대로다
    deal_after = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)
    assert deal_after.updated_at == deal_before.updated_at


async def test_update_action_by_admin_logs_admin_as_changer(action_env: ActionEnv) -> None:
    """admin이 남의 Action을 고쳐도 담당자는 그대로이고 변경자는 admin이다.

    테스트 코드: AC-055
    """
    # given: KIM이 남긴 Action
    action = await action_env.act(KIM)

    # when: admin이 내용을 고친다
    await action_env.update_as(action.id, BOSS, **CHANGE)

    # then: 담당자는 KIM 그대로이고 내용이 바뀐다
    stored = await action_env.stored(action.id)
    assert stored.actor_user_id == KIM.user_id  # 담당자는 그대로
    assert stored.content.action == "제안 발표"
    # then: 이력 변경자는 admin이다
    assert (await action_env.action_entries())[-1].changed_by == BOSS.user_id


async def test_update_action_by_other_sales_is_forbidden_and_changes_nothing(
    action_env: ActionEnv,
) -> None:
    """다른 sales의 수정은 403이고 Action·이력이 그대로다.

    테스트 코드: AC-056
    """
    # given: KIM이 남긴 Action과 수정 전 이력
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    # when·then: 다른 sales가 고치면 수정 권한 오류다
    with raises_with(DealActionEditForbiddenError, EDIT_FORBIDDEN):
        await action_env.update_as(action.id, PARK, **CHANGE)

    # then: 내용·수정 시각·이력이 그대로다
    stored = await action_env.stored(action.id)
    assert stored.content == action.content
    assert stored.updated_at == action.updated_at
    assert await action_env.rows() == rows_before


async def test_update_action_by_other_sales_is_forbidden_before_validation(
    action_env: ActionEnv,
) -> None:
    """다른 sales의 수정은 본문이 잘못돼도 403이다.

    테스트 코드: AC-056
    """
    # given: KIM이 남긴 Action
    action = await action_env.act(KIM)

    # when·then: 다른 sales가 빈 진행사항으로 고쳐도 검증 오류가 아닌 수정 권한 오류다
    with raises_with(DealActionEditForbiddenError, EDIT_FORBIDDEN):
        await action_env.update_as(action.id, PARK, action="   ")


async def test_update_missing_action_is_not_found_before_forbidden(action_env: ActionEnv) -> None:
    """없는 Action의 수정은 권한 확인보다 먼저 404다.

    테스트 코드: AC-057
    """
    # given: 존재하지 않는 Action id
    missing = DealActionId(new_id())

    # when·then: 다른 sales가 없는 id를 고치면 Action 없음 오류다
    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.update_as(missing, PARK, **CHANGE)


async def test_update_action_by_a_read_only_user_is_forbidden_even_for_own_id(
    action_env: ActionEnv,
) -> None:
    """읽기 전용 user는 자기 id의 Action도 고칠 수 없다.

    테스트 코드: AC-058
    """
    # given: user가 담당자로 된 Action
    own = make_deal_action(deal_code=action_env.deal.item.deal.id, actor_user_id=VIEWER.user_id)
    await action_env.env.uow.deal_actions.add(own)

    # when·then: user가 그 Action을 고치면 수정 권한 오류다
    with pytest.raises(DealActionEditForbiddenError):
        await action_env.update_as(own.id, VIEWER, **CHANGE)


async def test_update_action_by_owner_with_blank_progress_is_a_validation_error(
    action_env: ActionEnv,
) -> None:
    """진행사항·Next Action을 모두 비워 고치면 거절되고 Action은 그대로다.

    테스트 코드: AC-048
    """
    # given: KIM이 남긴 Action
    action = await action_env.act(KIM)

    # when·then: 진행사항·Next Action·Due를 모두 비워 고치면 내용 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.update_as(action.id, KIM, action="  ", next_action="", due_date=None)

    # then: Action 내용이 그대로다
    assert (await action_env.stored(action.id)).content == action.content


async def test_update_action_without_due_date_is_a_validation_error(
    action_env: ActionEnv,
) -> None:
    """Due Date를 비워 고치면 Due Date 필수 오류다.

    테스트 코드: AC-048
    """
    # given: Next Action이 있는 Action
    action = await action_env.act(KIM)

    # when·then: Due Date를 비워 고치면 Due Date 필수 오류다
    with raises_with(InvalidValueError, DUE_DATE_REQUIRED):
        await action_env.update_as(action.id, KIM, due_date=None)


async def test_update_action_without_change_logs_nothing(action_env: ActionEnv) -> None:
    """내용이 같은 수정은 이력도 수정 시각도 바꾸지 않는다.

    테스트 코드: AC-047
    """
    # given: KIM이 남긴 Action과 수정 전 이력
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    # when: 같은 내용으로 고친다
    result = await action_env.update_as(action.id, KIM)  # 같은 내용

    # then: 이력과 수정 시각이 그대로다
    assert await action_env.rows() == rows_before
    assert (await action_env.stored(action.id)).updated_at == action.updated_at
    assert result.updated_at == action.updated_at


async def test_update_action_with_content_equal_after_trim_logs_nothing(
    action_env: ActionEnv,
) -> None:
    """앞뒤 공백만 다른 수정은 이력도 수정 시각도 바꾸지 않는다.

    테스트 코드: AC-047
    """
    # given: KIM이 남긴 Action과 수정 전 이력
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    # when: 앞뒤 공백만 다른 내용으로 고친다
    await action_env.update_as(action.id, KIM, action="  킥오프 미팅  ")

    # then: 이력과 수정 시각이 그대로다
    assert await action_env.rows() == rows_before
    assert (await action_env.stored(action.id)).updated_at == action.updated_at


async def test_update_action_saves_long_text_in_full_and_clips_only_the_history(
    action_env: ActionEnv,
) -> None:
    """길이 상한 없이 저장하고 이력만 1,000자로 자른다.

    테스트 코드: AC-049
    """
    # given: KIM이 남긴 Action
    action = await action_env.act(KIM)

    # when: 진행사항 5,000자로 고친다
    await action_env.update_as(action.id, KIM, action="가" * 5_000)

    # then: 원문은 잘리지 않고 저장된다
    stored = await action_env.stored(action.id)
    assert stored.content.action is not None
    assert len(stored.content.action) == 5_000
    # then: 이력의 변경 후만 1,000자에서 "…"로 끝난다
    (_, _, _, after) = (await action_env.rows())[-1]
    assert len(after) == 1_000
    assert after.endswith("…")


async def test_a_change_visible_only_after_the_history_limit_still_logs_one_entry(
    action_env: ActionEnv,
) -> None:
    """1,000자 뒤에서만 달라진 수정도 이력 1건을 남긴다.

    테스트 코드: AC-049
    """
    # given: 요약이 1,000자를 넘는 Action과 이력 건수
    action = await action_env.act(KIM, action="가" * 2_000)
    entries_before = len(await action_env.action_entries())

    # when: 1,000자 뒤의 글자만 바꿔 고친다
    await action_env.update_as(action.id, KIM, action="가" * 1_999 + "나")

    # then: 이력이 1건 늘고 원문은 바뀐 값이다
    assert len(await action_env.action_entries()) == entries_before + 1
    stored_progress = (await action_env.stored(action.id)).content.action
    assert stored_progress is not None
    assert stored_progress.endswith("나")


async def test_update_clears_next_action(action_env: ActionEnv) -> None:
    """수정으로 Next Action을 비우면 Due·상태가 null이 된다.

    테스트 코드: AC-050
    """
    # given: Open Next Action이 있는 Action
    action = await action_env.act(KIM)

    # when: Next Action과 Due를 비워 고친다
    await action_env.update_as(action.id, KIM, next_action="", due_date=None)

    # then: Next Action·Due·상태가 모두 비고 이력은 수정 줄이다
    stored = await action_env.stored(action.id)
    assert stored.content.next_action is None
    assert stored.content.due_date is None
    assert stored.next_action_state is None
    assert (await action_env.rows())[-1][3] == "수정: 미팅 · 킥오프 미팅"


async def test_update_clearing_next_action_of_a_closed_one_removes_status_and_time(
    action_env: ActionEnv,
) -> None:
    """종료한 Next Action을 비우면 상태와 종료 시각도 사라진다.

    테스트 코드: AC-050
    """
    # given: 종료(수행)로 닫은 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done")

    # when: Next Action과 Due를 비워 고친다
    await action_env.update_as(action.id, KIM, next_action="", due_date=None)

    # then: 상태와 종료 시각이 없다
    assert (await action_env.stored(action.id)).next_action_state is None


async def test_update_adding_next_action_to_a_progress_only_action_opens_it(
    action_env: ActionEnv,
) -> None:
    """진행사항만 Action에 Next Action을 채우면 Open이 된다.

    테스트 코드: AC-051
    """
    # given: 진행사항만 있는 Action
    action = await action_env.act(KIM, next_action="")

    # when: Next Action과 Due를 채워 고친다
    await action_env.update_as(action.id, KIM, next_action="새 계획", due_date=date(2026, 3, 1))

    # then: 상태는 Open이다
    assert (await action_env.stored(action.id)).next_action_state == NextActionState.open()


async def test_update_next_action_text_of_a_closed_one_keeps_status_and_time(
    action_env: ActionEnv,
) -> None:
    """종료한 Next Action의 내용을 고쳐도 종료 상태와 시각은 그대로다.

    테스트 코드: AC-052
    """
    # given: 미수행으로 닫은 Action
    action = await action_env.act(KIM)
    closed = await action_env.set_status(action.id, KIM, "not_done", "접음")

    # when: Next Action 내용과 Due를 고친다
    await action_env.update_as(action.id, KIM, next_action="바뀐 계획", due_date=date(2026, 5, 1))

    # then: 내용은 바뀌고 상태와 종료 시각은 그대로다
    stored = await action_env.stored(action.id)
    assert stored.content.next_action == "바뀐 계획"
    assert stored.next_action_state == closed.next_action_state
    assert stored.next_action_state is not None
    assert stored.next_action_state.status is NextActionStatus.NOT_DONE


async def test_update_to_progress_only_content_is_accepted(action_env: ActionEnv) -> None:
    """진행사항만 있는 내용으로 고칠 수 있다."""
    # given: KIM이 남긴 기본 Action
    action = await action_env.act(KIM)

    # when: Next Action을 비우고 진행사항을 바꿔 고친다
    updated = await action_env.update_as(action.id, KIM, action="진행만", next_action="")

    # then: 진행사항만 남는다
    assert updated.content.action == "진행만"
    assert updated.content.next_action is None


async def test_update_due_date_without_next_action_is_a_validation_error(
    action_env: ActionEnv,
) -> None:
    """Next Action 없이 Due Date만 남기면 거절되고 Action은 그대로다.

    테스트 코드: AC-048
    """
    # given: KIM이 남긴 Action
    action = await action_env.act(KIM)

    # when·then: Next Action만 비우고 Due를 남겨 고치면 Due 금지 오류다
    with raises_with(InvalidValueError, DUE_WITHOUT_NEXT):
        await action_env.update_as(action.id, KIM, next_action="", due_date=date(2026, 2, 1))

    # then: Action 내용이 그대로다
    assert (await action_env.stored(action.id)).content == action.content


async def test_the_actor_can_update_their_own_action_when_not_the_deal_owner(
    action_env: ActionEnv,
) -> None:
    """Deal Owner가 아니어도 자기 Action은 고칠 수 있다.

    테스트 코드: AC-055
    """
    # given: Owner(KIM)가 아닌 sales가 남긴 Action
    action = await action_env.act(PARK)

    # when: 그 sales가 진행사항을 고친다
    await action_env.update_as(action.id, PARK, action="내가 고침")

    # then: 내용이 바뀌고 이력 변경자는 그 sales다
    assert (await action_env.stored(action.id)).content.action == "내가 고침"
    assert (await action_env.action_entries())[-1].changed_by == PARK.user_id


async def test_filling_the_progress_of_a_next_only_action_keeps_it_open(
    action_env: ActionEnv,
) -> None:
    """Next Action만 Action에 진행사항을 채워도 상태는 Open 그대로다.

    테스트 코드: AC-051
    """
    # given: Next Action만 있는 Action
    action = await action_env.act(KIM, action="")

    # when: 진행사항을 채워 고친다
    await action_env.update_as(action.id, KIM, action="진행 내용")

    # then: 상태는 Open 그대로다
    assert (await action_env.stored(action.id)).next_action_state == NextActionState.open()


async def test_update_leaves_the_comments_alone_and_the_summary_has_no_memo_part(
    action_env: ActionEnv,
) -> None:
    """Action 수정은 Comment를 바꾸지 않고 수정 이력 요약에 "Memo"가 없다.

    테스트 코드: CM-038
    """
    # given: KIM의 Action과 그 Action의 Action Comment "자료 전달"
    from tests.factories_comment import make_comment  # noqa: PLC0415

    action = await action_env.act(KIM)
    comment = make_comment(deal_code=action.deal_code, action_id=action.id, author=KIM.user_id)
    await action_env.env.uow.deal_comments.add(comment)

    # when: KIM이 진행사항을 고친다
    updated = await action_env.update_as(action.id, KIM, action="바뀐 진행")

    # then: Comment는 그대로이고 Action 내용에 memo가 없다
    stored = await action_env.env.uow.deal_comments.get(comment.id)
    assert (stored.body, stored.updated_at) == (comment.body, comment.updated_at)
    assert not hasattr(updated.content, "memo")
    # then: 수정 이력 요약에 Memo가 없다
    after = (await action_env.rows())[-1][3]
    assert "Memo" not in after
    assert after.startswith("수정: 미팅 · 바뀐 진행")
