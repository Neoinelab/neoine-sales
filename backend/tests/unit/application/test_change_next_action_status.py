"""ChangeNextActionStatus: 작성자·admin만, 404 -> 403 -> 422/409 순서, History 한 건."""

from datetime import date, datetime, timedelta, timezone
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
    from collections.abc import Callable

    from tests.unit.application.action_env import ActionEnv

KST = timezone(timedelta(hours=9))
STATUS_FORBIDDEN = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."
NO_NEXT_ACTION = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."
OPEN_WITH_COMMENT = "Open으로 되돌릴 때는 Comment를 남길 수 없습니다."
NUL_COMMENT = "Comment에는 NUL 문자를 쓸 수 없습니다"
DUE = "(Due 2026-01-15)"


async def _comments_of(action_env: ActionEnv, action_id: DealActionId) -> list[str]:
    """그 Action에 연결된 Comment 본문."""
    found = await action_env.env.uow.deal_comments.list_for_deal(action_env.deal.item.deal.id)
    return [c.body for c in found if c.action_id == action_id]


async def test_actor_closes_and_history_written(action_env: ActionEnv) -> None:
    """작성자가 Comment와 함께 종료(수행)하면 상태·종료일이 바뀌고 Action Comment 1건과 이력
    2건(Next Action 줄, Comment 등록 줄)이 남는다.

    테스트 코드: CM-031, NA-017
    """
    # given: sales kim이 등록한 Open Action
    action = await action_env.act(KIM)
    commits = action_env.env.uow.commits
    before_rows = await action_env.rows()
    # when: kim이 상태를 done, Comment "전달 완료"로 바꾼다
    changed = await action_env.set_status(action.id, KIM, "done", "전달 완료")
    # then: 상태 done, 종료일은 요청 시각의 업무 날짜이고 응답도 같으며 내용은 그대로다
    stored = await action_env.stored(action.id)
    assert changed.id == action.id
    assert stored.next_action_state == NextActionState(
        status=NextActionStatus.DONE, closed_on=action_env.env.clock.now().astimezone().date()
    )
    assert changed.next_action_state == stored.next_action_state
    assert stored.content == action.content
    assert action_env.env.uow.commits == commits + 1
    # then: Action Comment "전달 완료" 1건(작성자 KIM, 시각 요청 시각)이 생긴다
    (comment,) = [
        c
        for c in await action_env.env.uow.deal_comments.list_for_deal(action.deal_code)
        if c.action_id == action.id
    ]
    assert (comment.body, comment.author_user_id) == ("전달 완료", KIM.user_id)
    assert comment.created_at == comment.updated_at == action_env.env.clock.now()
    # then: 이력은 Next Action 줄(변경 후는 라벨만) 다음에 Comment 등록 줄 순으로 2건 늘어난다
    rows = await action_env.rows()
    assert rows[:-2] == before_rows
    assert rows[-2:] == [
        ("action", "Next Action", f"요구사항 문서 전달 {DUE} · Open", "종료(수행)"),
        (
            "comment",
            f"Action Comment ({action.acted_on.isoformat()} 미팅)",
            "",
            "등록: 전달 완료",
        ),
    ]
    entries = (await action_env.entries())[-2:]
    assert {(e.changed_by, e.changed_at) for e in entries} == {
        (KIM.user_id, action_env.env.clock.now())
    }


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


@pytest.mark.parametrize("comment", ["", "   \n "])
async def test_closing_without_a_comment_makes_no_comment(
    action_env: ActionEnv, comment: str
) -> None:
    """비었거나 공백뿐인 종료 Comment는 Comment를 만들지 않고 종료만 한다.

    테스트 코드: CM-033
    """
    # given: Open Action
    action = await action_env.act(KIM)
    # when: 작성자가 not_done으로 바꾸며 빈 Comment 또는 공백뿐인 Comment를 보낸다
    await action_env.set_status(action.id, KIM, "not_done", comment)
    # then: 상태는 not_done, 종료일이 있고 내용은 그대로이며 Comment가 없다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState(
        status=NextActionStatus.NOT_DONE, closed_on=action_env.env.clock.now().astimezone().date()
    )
    assert stored.content == action.content
    assert await _comments_of(action_env, action.id) == []
    # then: 이력은 Next Action 줄 하나뿐이고 변경 후는 "종료(미수행)"다
    assert [row[0] for row in await action_env.rows()] == ["action", "action"]
    assert (await action_env.rows())[-1][3] == "종료(미수행)"


async def test_reopening_clears_closed_time_and_logs_the_change(action_env: ActionEnv) -> None:
    """Open으로 되돌리면 종료 시각이 없어지고 만든 Comment는 남으며 History가 한 건 남는다.

    테스트 코드: NA-005, NA-017
    """
    # given: Comment "끝"을 붙여 종료(수행)한 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done", "끝")
    # when: 작성자가 open으로 바꾼다
    await action_env.set_status(action.id, KIM, "open")
    # then: 상태는 open, 종료 시각은 null, Comment "끝"은 그대로, 이력은 종료(수행) -> Open이다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert await _comments_of(action_env, action.id) == ["끝"]
    assert (await action_env.rows())[-1][2:] == (f"요구사항 문서 전달 {DUE} · 종료(수행)", "Open")


async def test_each_status_change_logs_one_entry_with_the_fixed_wording(
    action_env: ActionEnv,
) -> None:
    """세 번 바꾸면(done+Comment, open, not_done) Next Action History가 세 건 차례로 늘고 문구가
    정해진 형식이다(변경 후는 라벨만).

    테스트 코드: NA-017
    """
    # given: Next Action "요구사항 문서 전달", Due 2026-01-15인 Open Action
    action = await action_env.act(KIM)
    base = len(await action_env.action_entries())
    # when: 작성자가 차례로 done+Comment "전달 완료", open, not_done(Comment 없음)으로 바꾼다
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
            "종료(수행)",
        ),
        ("action", "Next Action", f"요구사항 문서 전달 {DUE} · 종료(수행)", "Open"),
        ("action", "Next Action", f"요구사항 문서 전달 {DUE} · Open", "종료(미수행)"),
    ]
    assert {e.changed_by for e in entries} == {KIM.user_id}


async def test_a_long_closing_comment_is_clipped_in_history_but_kept_in_the_comment(
    action_env: ActionEnv,
) -> None:
    """1,000자를 넘는 종료 Comment는 이력 값만 잘리고 Comment 원문은 그대로다.

    테스트 코드: CM-011, CM-031
    """
    # given: Open Action
    action = await action_env.act(KIM)
    # when: 작성자가 1,500자 Comment로 종료(수행)한다
    await action_env.set_status(action.id, KIM, "done", "가" * 1_500)
    # then: Comment 등록 줄의 변경 후 값은 999자 + "…"이고 Comment에는 전체가 있다
    after = (await action_env.rows())[-1][3]
    assert len(after) == 1_000
    assert after.startswith("등록: 가가")
    assert after.endswith("…")
    assert await _comments_of(action_env, action.id) == ["가" * 1_500]


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
    # then: 내용·수행일·작성자·스냅숏은 등록 때와 같고 Deal 수정 시각은 그대로다
    stored = await action_env.stored(action.id)
    assert stored.content == action.content
    assert stored.acted_on == action.acted_on
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
    # when·then: sales park이 done, Comment "남의 것"으로 바꾸면 403 고정 문구다
    with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
        await action_env.set_status(action.id, PARK, "done", "남의 것")
    # then: 상태·내용·Comment 수·History·커밋이 그대로다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert stored.content == action.content
    assert await _comments_of(action_env, action.id) == []
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
    """Open Action을 open으로 바꾸면 409이고 Comment 수·History가 그대로다.

    테스트 코드: NA-007
    """
    # given: Open Action
    action = await action_env.act(KIM)
    rows = await action_env.rows()
    # when·then: 작성자가 open으로 바꾸면 409 "이미 Open 상태입니다."다
    with raises_with(InvalidStateError, "이미 Open 상태입니다."):
        await action_env.set_status(action.id, KIM, "open")
    # then: History·Comment 수와 내용이 그대로다
    assert await action_env.rows() == rows
    assert await _comments_of(action_env, action.id) == []
    assert (await action_env.stored(action.id)).content == action.content


async def test_same_closed_status_conflicts_without_change(action_env: ActionEnv) -> None:
    """종료(수행) Action을 Comment와 함께 done으로 바꾸면 409이고 Comment·종료 시각·이력이 그대로다.

    테스트 코드: NA-007
    """
    # given: Comment "첫 종료"로 종료(수행)된 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done", "첫 종료")
    closed = (await action_env.stored(action.id)).next_action_state
    rows = await action_env.rows()
    # when·then: 작성자가 done, Comment "또 종료"로 바꾸면 409 "이미 종료(수행) 상태입니다."다
    with raises_with(InvalidStateError, "이미 종료(수행) 상태입니다."):
        await action_env.set_status(action.id, KIM, "done", "또 종료")
    # then: Comment 수·종료 시각·History 건수가 그대로다
    stored = await action_env.stored(action.id)
    assert await _comments_of(action_env, action.id) == ["첫 종료"]
    assert stored.next_action_state == closed
    assert await action_env.rows() == rows


async def test_action_without_next_action_conflicts_without_change(
    action_env: ActionEnv,
) -> None:
    """Next Action이 없는 Action의 상태를 바꾸면 409이고 Comment 수·History가 그대로다.

    테스트 코드: NA-008
    """
    # given: 진행사항만 Action
    action = await action_env.act(KIM, next_action="")
    rows = await action_env.rows()
    # when·then: 작성자가 done, Comment "메모"로 바꾸면 409다
    with raises_with(InvalidStateError, NO_NEXT_ACTION):
        await action_env.set_status(action.id, KIM, "done", "메모")
    # then: 내용·Comment 수·History가 그대로다
    assert (await action_env.stored(action.id)).content == action.content
    assert await _comments_of(action_env, action.id) == []
    assert await action_env.rows() == rows


async def test_open_with_a_comment_is_a_validation_error(action_env: ActionEnv) -> None:
    """Open으로 되돌리며 Comment를 보내면 422이고 상태·종료 시각·Comment 수·History가 그대로다.

    테스트 코드: NA-006, CM-034
    """
    # given: 종료(수행)된 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done")
    before = await action_env.stored(action.id)
    rows = await action_env.rows()
    # when·then: 작성자가 open, Comment "되돌림"으로 바꾸면 422 문구다
    with raises_with(InvalidValueError, OPEN_WITH_COMMENT):
        await action_env.set_status(action.id, KIM, "open", "되돌림")
    # then: 상태·종료 시각·Comment 수·History가 그대로다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == before.next_action_state
    assert await _comments_of(action_env, action.id) == []
    assert await action_env.rows() == rows


async def test_open_with_a_blank_comment_is_allowed(action_env: ActionEnv) -> None:
    """Open으로 되돌릴 때 공백뿐인 Comment는 허용되고 Comment가 생기지 않는다.

    테스트 코드: NA-006, CM-034
    """
    # given: 종료(수행)된 Action
    action = await action_env.act(KIM)
    await action_env.set_status(action.id, KIM, "done")
    # when: 작성자가 open, Comment "   "로 바꾼다
    await action_env.set_status(action.id, KIM, "open", "   ")
    # then: Open이 되고 Comment는 없다
    assert (await action_env.stored(action.id)).next_action_state == NextActionState.open()
    assert await _comments_of(action_env, action.id) == []


async def test_closing_comment_with_nul_is_rejected_without_change(
    action_env: ActionEnv,
) -> None:
    """종료 Comment에 NUL 문자가 있으면 422 invalid-value이고 Action·Comment·History가 그대로다.

    테스트 코드: NA-009
    """
    # given: Open Action
    action = await action_env.act(KIM)
    rows = await action_env.rows()
    # when·then: 작성자가 done, Comment "가\x00나"로 바꾸면 422 NUL 문구다
    with raises_with(InvalidValueError, NUL_COMMENT):
        await action_env.set_status(action.id, KIM, "done", "가\x00나")
    # then: 상태·내용·Comment 수·History가 그대로다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state == NextActionState.open()
    assert stored.content == action.content
    assert await _comments_of(action_env, action.id) == []
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


async def test_closed_on_is_the_business_date_of_the_request_and_reopen_clears_it(
    action_env: ActionEnv, local_tz: Callable[[str], None]
) -> None:
    """종료하면 종료일은 요청의 업무 날짜(수행일이 아님)이고 Open으로 되돌리면 비운다.

    테스트 코드: NA-070
    """
    # given: 서울 시간대, 1월 1일에 수행한 Open Action이 있고 시계가 1월 3일 01:00(서울)로 흘렀다
    local_tz("Asia/Seoul")
    action = await action_env.act(KIM)
    action_env.set_clock(datetime(2026, 1, 3, 1, 0, tzinfo=KST))

    # when: 종료(수행)한다
    done = await action_env.set_status(action.id, KIM, "done")
    # then: 종료일은 요청의 업무 날짜 1월 3일(date)이고 수행일은 1월 1일 그대로다
    assert done.next_action_state == NextActionState(
        NextActionStatus.DONE, closed_on=date(2026, 1, 3)
    )
    assert (await action_env.stored(action.id)).acted_on == date(2026, 1, 1)

    # when: 다음 날(1월 4일) 종료(미수행)로 바꾼 뒤 Open으로 되돌린다
    action_env.set_clock(datetime(2026, 1, 4, 10, 0, tzinfo=KST))
    not_done = await action_env.set_status(action.id, KIM, "not_done")
    reopened = await action_env.set_status(action.id, KIM, "open")
    # then: 미수행의 종료일은 1월 4일이고 Open이면 종료일이 없다
    assert not_done.next_action_state == NextActionState(
        NextActionStatus.NOT_DONE, closed_on=date(2026, 1, 4)
    )
    assert reopened.next_action_state == NextActionState.open()
    assert reopened.next_action_state is not None
    assert reopened.next_action_state.closed_on is None
