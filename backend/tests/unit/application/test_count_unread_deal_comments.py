"""CountUnreadDealComments: Deal의 읽지 않은 Comment 수와 Action별 수(CM-R29).

`execute(code) -> UnreadCommentCounts`(`.total`, `.by_action`: Action id -> 1 이상의 수).
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.deal.errors import DealNotFoundError
from tests.support.expect import raises_with
from tests.unit.application.action_env import BOSS, KIM, PARK
from tests.unit.application.comment_env import DEAL_NOT_FOUND

if TYPE_CHECKING:
    from tests.unit.application.comment_env import CommentEnv


async def test_counts_unread_for_the_deal_and_per_action_without_other_deals(
    comment_env: CommentEnv,
) -> None:
    """읽지 않은 수는 Deal 전체와 Action별(1 이상만)로 주고 다른 Deal 것은 섞이지 않는다.

    테스트 코드: CM-055
    """
    # given: D에 읽지 않은 Deal Comment 1건, A의 읽지 않은 Comment 2건, P의 읽은 Comment 1건
    action_p = await comment_env.actions.act(PARK, action="현장 점검", next_action="")
    await comment_env.say(PARK, "deal-unread")
    await comment_env.say(PARK, "a-unread-1", action_id=comment_env.action.id)
    await comment_env.say(BOSS, "a-unread-2", action_id=comment_env.action.id)
    await comment_env.say(KIM, "p-read", action_id=action_p.id)  # Owner가 쓴 것은 읽음
    # given: 다른 Deal E에 읽지 않은 Comment 3건
    other_code, other_action = await comment_env.other_deal()
    for n in range(2):
        await comment_env.say(PARK, f"e{n}", code=other_code)
    await comment_env.say(PARK, "e-action", code=other_code, action_id=other_action.id)

    # when: D의 읽지 않은 수를 센다
    counts = await comment_env.counts.execute(comment_env.code)

    # then: 전체 3, Action별은 A만 2다(P는 0이라 빠진다)
    assert counts.total == 3
    assert dict(counts.by_action) == {comment_env.action.id: 2}


async def test_a_deal_without_unread_comments_has_zero_and_an_empty_by_action(
    comment_env: CommentEnv,
) -> None:
    """읽지 않은 Comment가 없으면 total 0이고 by_action이 비어 있다.

    테스트 코드: CM-055
    """
    # given: Owner가 쓴(읽은) Comment만 있다
    await comment_env.say(KIM, "mine", action_id=comment_env.action.id)

    # when: 센다
    counts = await comment_env.counts.execute(comment_env.code)

    # then: 0과 빈 by_action이다
    assert counts.total == 0
    assert dict(counts.by_action) == {}


async def test_marking_read_lowers_the_counts(comment_env: CommentEnv) -> None:
    """Owner가 읽음 처리하면 그 Comment만큼 전체·Action별 수가 줄어든다.

    테스트 코드: CM-055, CM-049
    """
    # given: A의 읽지 않은 Comment 2건
    first = await comment_env.say(PARK, "a1", action_id=comment_env.action.id)
    await comment_env.say(PARK, "a2", action_id=comment_env.action.id)

    # when: 하나를 읽음 처리한다
    await comment_env.mark_read.execute(comment_env.code, KIM, [first.id])
    counts = await comment_env.counts.execute(comment_env.code)

    # then: 전체 1, A 1이다
    assert counts.total == 1
    assert dict(counts.by_action) == {comment_env.action.id: 1}


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_counting_a_missing_deal_is_not_found(comment_env: CommentEnv, code: str) -> None:
    """없는 Deal·형식이 틀린 code는 404다.

    테스트 코드: CM-055
    """
    # when·then: 없는 Deal을 세면 Deal 없음 오류다
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await comment_env.counts.execute(code)
