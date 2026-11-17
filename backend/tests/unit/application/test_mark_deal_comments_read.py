"""MarkDealCommentsRead: 그 Deal의 현재 Owner만 읽음 처리한다(CM-R28).

판정 순서는 없는 Deal(404) -> Owner가 아님(403) -> 처리다. user 403·CSRF·요청 형식 422는 웹 규칙이라
`web/test_deal_comment_read_routes.py`가 본다. 시그니처는 `execute(code, actor, comment_ids)`다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_comment.errors import DealCommentReadForbiddenError
from app.domain.deal_comment.values import DealCommentId
from tests.support.expect import raises_with
from tests.support.ids import MAX_ID
from tests.unit.application.action_env import BOSS, KIM, PARK
from tests.unit.application.comment_env import DEAL_NOT_FOUND, READ_FORBIDDEN

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.domain.deal_comment.entities import DealComment
    from tests.unit.application.comment_env import CommentEnv


async def _unread_pair(comment_env: CommentEnv) -> tuple[DealComment, DealComment]:
    """Owner가 아닌 PARK의 A Comment p1과 admin의 Deal Comment r1(둘 다 읽지 않음)."""
    p1 = await comment_env.say(PARK, "p1", action_id=comment_env.action.id)
    r1 = await comment_env.say(BOSS, "r1")
    return p1, r1


async def test_the_owner_marks_comments_read_and_everyone_sees_them_as_read(
    comment_env: CommentEnv,
) -> None:
    """Owner가 읽음 처리하면 read_at이 요청 시각으로 채워져 누가 읽어도 읽음이다.

    테스트 코드: CM-049
    """
    # given: 읽지 않은 p1·r1
    p1, r1 = await _unread_pair(comment_env)
    comment_env.clock.advance(60)

    # when: KIM(Owner)이 [p1, r1]을 읽음 처리한다
    await comment_env.mark_read.execute(comment_env.code, KIM, [p1.id, r1.id])

    # then: 둘 다 요청 시각으로 읽음이다(목록에서 읽어도 같다)
    now = comment_env.clock.now()
    views = await comment_env.list.execute(comment_env.code, None)
    listed = {v.comment.id: v.comment.read_at for v in views}
    assert listed[p1.id] == listed[r1.id] == now


@pytest.mark.parametrize("who", [PARK, BOSS], ids=["other-sales", "admin"])
async def test_a_non_owner_is_forbidden_and_nothing_changes(
    comment_env: CommentEnv, who: Actor
) -> None:
    """Owner가 아닌 sales·admin의 읽음 처리는 403이고 read_at이 바뀌지 않는다.

    테스트 코드: CM-050
    """
    # given: 읽지 않은 p1
    p1, _ = await _unread_pair(comment_env)
    commits = comment_env.uow.commits

    # when·then: Owner가 아닌 사람이 처리하면 403이다
    with raises_with(DealCommentReadForbiddenError, READ_FORBIDDEN):
        await comment_env.mark_read.execute(comment_env.code, who, [p1.id])

    # then: p1은 읽지 않음 그대로이고 커밋이 없다
    assert await comment_env.read_at(p1.id) is None
    assert comment_env.uow.commits == commits


async def test_other_deals_missing_and_already_read_ids_are_skipped_without_error(
    comment_env: CommentEnv,
) -> None:
    """다른 Deal·없는·이미 읽은 id는 건너뛰고 중복도 한 번으로 보며 이미 읽은 read_at은 그대로다.

    테스트 코드: CM-051
    """
    # given: p1은 이미 읽음(R1), r1은 읽지 않음, 다른 Deal E에 읽지 않은 Comment e1
    p1, r1 = await _unread_pair(comment_env)
    comment_env.clock.advance(60)
    await comment_env.mark_read.execute(comment_env.code, KIM, [p1.id])
    first_read = comment_env.clock.now()
    other_code, _ = await comment_env.other_deal()
    e1 = await comment_env.say(PARK, "e1", code=other_code)
    comment_env.clock.advance(60)

    # when: [p1, p1, e1, 상한 id, r1]을 D로 읽음 처리한다
    await comment_env.mark_read.execute(
        comment_env.code, KIM, [p1.id, p1.id, e1.id, DealCommentId(MAX_ID), r1.id]
    )

    # then: p1은 처음 값 그대로, r1은 이번 시각, e1은 읽지 않음 그대로다
    assert await comment_env.read_at(p1.id) == first_read
    assert await comment_env.read_at(r1.id) == comment_env.clock.now()
    assert await comment_env.read_at(e1.id) is None


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_a_missing_deal_is_not_found_before_the_owner_check(
    comment_env: CommentEnv, code: str
) -> None:
    """없는 Deal·형식이 틀린 code는 Owner 판정보다 먼저 404이고 아무 read_at도 바뀌지 않는다.

    테스트 코드: CM-052
    """
    # given: 읽지 않은 p1
    p1, _ = await _unread_pair(comment_env)

    # when·then: Owner가 아닌 PARK이 없는 Deal로 보내도 404다
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await comment_env.mark_read.execute(code, PARK, [p1.id])

    # then: p1은 읽지 않음 그대로다
    assert await comment_env.read_at(p1.id) is None


async def test_changing_the_owner_keeps_read_states_and_only_the_new_owner_marks_read(
    comment_env: CommentEnv,
) -> None:
    """Owner가 바뀌어도 읽음 상태는 그대로, 읽음 처리는 새 Owner만, 새 Owner의 Comment는 읽음이다.

    테스트 코드: CM-053
    """
    # given: KIM이 p1을 읽음 처리했고 읽지 않은 r1이 있다
    p1, r1 = await _unread_pair(comment_env)
    await comment_env.mark_read.execute(comment_env.code, KIM, [p1.id])
    p1_read_at = await comment_env.read_at(p1.id)

    # when: D의 Owner를 PARK으로 바꾼다
    await comment_env.set_owner(PARK)

    # then: Owner를 바꾼 뒤에도 p1은 읽음(같은 시각), r1은 읽지 않음이다
    assert await comment_env.read_at(p1.id) == p1_read_at
    assert await comment_env.read_at(r1.id) is None

    # when·then: 이전 Owner KIM의 읽음 처리는 403이다
    with raises_with(DealCommentReadForbiddenError, READ_FORBIDDEN):
        await comment_env.mark_read.execute(comment_env.code, KIM, [r1.id])
    assert await comment_env.read_at(r1.id) is None

    # when: 새 Owner PARK이 읽음 처리하고 Comment p2를 쓴다
    comment_env.clock.advance(60)
    await comment_env.mark_read.execute(comment_env.code, PARK, [r1.id])
    marked_at = comment_env.clock.now()
    p2 = await comment_env.say(PARK, "p2")

    # then: r1은 읽음이 되고 p2는 읽음으로 생긴다
    assert await comment_env.read_at(r1.id) == marked_at
    assert await comment_env.read_at(p2.id) == p2.created_at


async def test_marking_read_changes_neither_history_nor_deal_action_nor_comment_body(
    comment_env: CommentEnv,
) -> None:
    """읽음 처리는 History·Deal·Action·Comment 본문과 수정 시각을 바꾸지 않는다.

    테스트 코드: CM-054
    """
    # given: 읽지 않은 p1과 현재 이력 수, Deal·Action 수정 시각
    p1, _ = await _unread_pair(comment_env)
    code = DealCode(comment_env.code)
    deal_before = await comment_env.uow.deals.get(code)
    action_before = await comment_env.uow.deal_actions.get(comment_env.action.id)
    rows = await comment_env.rows()
    comment_env.clock.advance(60)

    # when: Owner가 p1을 읽음 처리한다
    await comment_env.mark_read.execute(comment_env.code, KIM, [p1.id])

    # then: 이력 수·Deal·Action·Comment의 본문과 수정 시각이 그대로다
    assert await comment_env.rows() == rows
    deal_after = await comment_env.uow.deals.get(code)
    action_after = await comment_env.uow.deal_actions.get(comment_env.action.id)
    assert deal_after.updated_at == deal_before.updated_at
    assert action_after.updated_at == action_before.updated_at
    stored = await comment_env.uow.deal_comments.get(p1.id)
    assert (stored.body, stored.updated_at) == (p1.body, p1.updated_at)
