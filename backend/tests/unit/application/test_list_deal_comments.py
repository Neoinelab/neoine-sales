"""ListDealComments·GetDealComment: Deal 소속 Comment 목록(최근순)과 한 건 조회.

둘 다 `DealCommentView`(`.comment`, `.action` = 연결 Action 요약 또는 None)를 돌려준다(CM-R9).
"""

import pytest

from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.value_objects import DealActionId
from app.domain.deal_comment.errors import DealCommentNotFoundError
from app.domain.deal_comment.values import DealCommentId
from tests.factories import NOW
from tests.support.expect import raises_with
from tests.support.ids import MAX_ID, MISSING_ID
from tests.unit.application.action_env import KIM, PARK
from tests.unit.application.comment_env import DEAL_NOT_FOUND, NOT_FOUND, CommentEnv


async def _seed(comment_env: CommentEnv) -> tuple[str, list[str]]:
    """D에 c1(Deal), c2(A의 Action), c3(Deal, c2와 같은 시각·더 큰 id), E에 c4를 둔다."""
    other_code, _ = await comment_env.other_deal()
    c1 = await comment_env.say(KIM, "c1")
    c2 = await comment_env.say(KIM, "c2", action_id=comment_env.action.id)
    c3 = await comment_env.say(PARK, "c3", advance=0)  # c2와 같은 시각
    await comment_env.say(KIM, "c4", code=other_code)
    return other_code, [str(c1.id), str(c2.id), str(c3.id)]


async def test_the_list_returns_all_comments_of_the_deal_newest_first_and_none_of_others(
    comment_env: CommentEnv,
) -> None:
    """목록은 Deal 소속 Comment 전부를 최근순(created_at, id 내림차순)으로 주고 다른 Deal 것은 뺀다.

    테스트 코드: CM-013
    """
    # given: D에 c1·c2(Action)·c3(c2와 같은 시각, 더 큰 id), E에 c4
    await _seed(comment_env)

    # when: D의 목록을 읽는다
    found = await comment_env.list.execute(comment_env.code, None)

    # then: c3, c2, c1 순서이고 c4는 없다(같은 시각에서는 id가 큰 것이 먼저)
    assert [v.comment.body for v in found] == ["c3", "c2", "c1"]
    # then: 세 건 모두 D 소속이고 c2만 Action에 연결되어 있다
    assert {v.comment.deal_code.value for v in found} == {comment_env.code}
    assert [v.comment.action_id for v in found] == [None, comment_env.action.id, None]
    assert found[0].comment.created_at == found[1].comment.created_at
    assert found[0].comment.id > found[1].comment.id
    # then: c2의 연결 Action 요약은 Action A의 값이고 Deal Comment는 요약이 없다
    assert found[1].action is not None
    assert found[1].action.id == comment_env.action.id
    assert found[0].action is None
    assert found[2].action is None


async def test_the_action_filter_returns_only_that_actions_comments(
    comment_env: CommentEnv,
) -> None:
    """action_id로 거르면 그 Action의 Comment만 나오고 그 Deal에 없는 Action id는 0건이다.

    테스트 코드: CM-014
    """
    # given: CM-013의 Comment들과 다른 Deal의 Action B
    await _seed(comment_env)
    _, foreign = await comment_env.other_deal()

    # when: A, B(다른 Deal), 없는 id로 거른다
    of_a = await comment_env.list.execute(comment_env.code, comment_env.action.id)
    of_b = await comment_env.list.execute(comment_env.code, foreign.id)
    of_missing = await comment_env.list.execute(comment_env.code, DealActionId(MISSING_ID))

    # then: A는 c2만, 나머지는 빈 목록이다
    assert [v.comment.body for v in of_a] == ["c2"]
    assert list(of_b) == []
    assert list(of_missing) == []


async def test_the_linked_action_summary_is_the_actions_current_values_and_null_for_a_deal_comment(
    comment_env: CommentEnv,
) -> None:
    """연결 Action 요약은 응답 시점 그 Action의 현재 값이고 Deal Comment는 요약이 없다.

    테스트 코드: CM-056
    """
    # given: A에 연결된 Comment p1과 Deal Comment k1, 이어서 KIM이 A의 진행사항을 고친다
    p1 = await comment_env.say(PARK, "p1", action_id=comment_env.action.id)
    k1 = await comment_env.say(KIM, "k1")
    await comment_env.actions.update_as(comment_env.action.id, KIM, action="킥오프 완료")

    # when: 한 건과 목록을 읽는다
    one = await comment_env.get.execute(p1.id)
    listed = {v.comment.id: v for v in await comment_env.list.execute(comment_env.code, None)}

    # then: 요약은 id·수행일·고친 진행사항·Next Action이다(한 건·목록 모두)
    for view in (one, listed[p1.id]):
        summary = view.action
        assert summary is not None
        assert summary.id == comment_env.action.id
        assert summary.acted_on == comment_env.action.acted_on
        assert summary.action == "킥오프 완료"
        assert summary.next_action == comment_env.action.content.next_action
    # then: Deal Comment의 요약은 없다
    assert listed[k1.id].action is None
    assert (await comment_env.get.execute(k1.id)).action is None


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_listing_a_missing_or_malformed_deal_is_not_found(
    comment_env: CommentEnv, code: str
) -> None:
    """없는 Deal·형식이 틀린 code의 목록은 404다.

    테스트 코드: CM-015
    """
    # when·then: 없는 Deal 목록은 Deal 없음 오류다
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await comment_env.list.execute(code, None)


async def test_get_returns_one_comment_and_a_missing_one_is_not_found(
    comment_env: CommentEnv,
) -> None:
    """한 건 조회는 그 Comment를 주고, 없는 id는 상한값이어도 NotFound다.

    테스트 코드: CM-015, CM-016
    """
    # given: Comment 한 건
    written = await comment_env.say(KIM, "예산 확인")

    # when: 그 id로 읽는다
    found = (await comment_env.get.execute(written.id)).comment

    # then: 같은 Comment다
    assert (found.id, found.body, found.author_user_id) == (written.id, "예산 확인", KIM.user_id)
    # when·then: 상한 id의 없는 Comment는 NotFound다
    with raises_with(DealCommentNotFoundError, NOT_FOUND):
        await comment_env.get.execute(DealCommentId(MAX_ID))


async def test_a_resigned_author_keeps_the_comment_readable(comment_env: CommentEnv) -> None:
    """작성자가 퇴사해도 Comment는 남아 읽힌다(작성자 행이 그대로 있다).

    테스트 코드: CM-017
    """
    # given: PARK이 쓴 Comment와 PARK의 퇴사
    written = await comment_env.say(PARK, "퇴사 전 글")
    park = await comment_env.uow.users.get(PARK.user_id)
    park.resign(NOW)
    await comment_env.uow.users.update(park)

    # when: 목록을 읽는다
    found = await comment_env.list.execute(comment_env.code, None)

    # then: Comment가 있고 작성자는 퇴사 처리된 사용자다
    assert [v.comment.id for v in found] == [written.id]
    assert (await comment_env.uow.users.get(found[0].comment.author_user_id)).deleted_at is not None
