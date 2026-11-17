"""DeleteDealComment: 작성자 본인 sales와 admin만, 물리 삭제와 이력, 판정 순서 404 -> 403."""

from typing import TYPE_CHECKING

import pytest
from app.domain.deal_comment.errors import (
    DealCommentDeleteForbiddenError,
    DealCommentNotFoundError,
)
from app.domain.deal_comment.values import DealCommentId

from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.action_env import BOSS, KIM, PARK
from tests.unit.application.comment_env import DELETE_FORBIDDEN, NOT_FOUND

if TYPE_CHECKING:
    from tests.unit.application.comment_env import CommentEnv


async def test_the_author_deletes_the_comment_and_the_history_keeps_the_body(
    comment_env: CommentEnv,
) -> None:
    """작성자가 지우면 행이 없어지고 이력에 본문과 "삭제"가 남으며 다시 지우면 404다.

    테스트 코드: CM-024
    """
    # given: KIM의 Deal Comment "예산 확인"
    written = await comment_env.say(KIM, "예산 확인")
    commits = comment_env.uow.commits
    comment_env.clock.advance(60)

    # when: KIM이 지운다
    await comment_env.delete.execute(written.id, KIM)

    # then: 한 건 조회가 NotFound이고 커밋은 1번이다
    with raises_with(DealCommentNotFoundError, NOT_FOUND):
        await comment_env.get.execute(written.id)
    assert comment_env.uow.commits == commits + 1
    # then: 이력 최신 줄은 (comment, "Comment", 본문, "삭제")이고 변경자는 KIM이다
    assert (await comment_env.comment_rows())[-1] == ("comment", "Comment", "예산 확인", "삭제")
    entry = (await comment_env.actions.entries())[-1]
    assert (entry.changed_by, entry.changed_at) == (KIM.user_id, comment_env.clock.now())
    # when·then: 같은 id를 다시 지우면 NotFound다
    with raises_with(DealCommentNotFoundError, NOT_FOUND):
        await comment_env.delete.execute(written.id, KIM)


async def test_another_sales_is_rejected_and_admin_deletes_others_comments(
    comment_env: CommentEnv,
) -> None:
    """다른 sales의 삭제는 403이고 Comment가 그대로이며, admin은 남의 Comment를 지운다.

    테스트 코드: CM-025
    """
    # given: KIM의 Comment k
    written = await comment_env.say(KIM, "원문")
    rows = await comment_env.rows()

    # when·then: PARK이 지우면 403이고 k와 이력이 그대로다
    with raises_with(DealCommentDeleteForbiddenError, DELETE_FORBIDDEN):
        await comment_env.delete.execute(written.id, PARK)
    assert [c.id for c in await comment_env.stored()] == [written.id]
    assert await comment_env.rows() == rows

    # when: admin이 지운다
    await comment_env.delete.execute(written.id, BOSS)

    # then: k가 없어지고 이력 변경자는 admin이다
    assert await comment_env.stored() == []
    assert (await comment_env.actions.entries())[-1].changed_by == BOSS.user_id


async def test_deleting_a_missing_comment_is_not_found(comment_env: CommentEnv) -> None:
    """없는 Comment의 삭제는 404다.

    테스트 코드: CM-024, CM-025
    """
    # when·then: 없는 id를 지우면 NotFound다
    with raises_with(DealCommentNotFoundError, NOT_FOUND):
        await comment_env.delete.execute(DealCommentId(MISSING_ID), KIM)


@pytest.mark.parametrize("target", ["deal", "action"])
async def test_deleting_one_comment_leaves_the_others(comment_env: CommentEnv, target: str) -> None:
    """하나를 지워도 같은 Deal의 다른 Comment는 그대로다.

    테스트 코드: CM-024
    """
    # given: Deal Comment와 Action Comment 하나씩
    deal_comment = await comment_env.say(KIM, "딜")
    action_comment = await comment_env.say(KIM, "액션", action_id=comment_env.action.id)
    victim, keeper = (
        (deal_comment, action_comment) if target == "deal" else (action_comment, deal_comment)
    )

    # when: 하나를 지운다
    await comment_env.delete.execute(victim.id, KIM)

    # then: 다른 하나만 남는다
    assert [c.id for c in await comment_env.stored()] == [keeper.id]
