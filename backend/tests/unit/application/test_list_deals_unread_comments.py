"""ListDeals: 목록 행의 읽지 않은 Comment 수 `item.unread_comment_count`(CM-R47).

값은 그 Deal 소속(Deal·Action Comment 모두)의 read_at이 없는 Comment 수이고,
목록 조건·정렬·total에는 영향이 없다. `comment_env` 위에서 `ListDeals`를 부른다.
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery, DealSort
from tests.unit.application.action_env import BOSS, KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.comment_env import CommentEnv


async def _counts(env: CommentEnv, query: DealQuery | None = None) -> dict[str, int]:
    page = await env.actions.env.list.execute(query or DealQuery(limit=200))
    return {v.item.deal.id.value: v.item.unread_comment_count for v in page.items}


async def test_a_row_counts_the_unread_deal_and_action_comments_of_that_deal(
    comment_env: CommentEnv,
) -> None:
    """목록 행 값은 그 Deal의 읽지 않은 Comment 수이고 comment-counts의 unread와 같다.

    테스트 코드: CM-085
    """
    # given: D에 PARK의 Deal Comment 1건·A의 Action Comment 2건(읽지 않음)
    # given: D에 Owner KIM이 쓴 Comment 1건(읽음)
    await comment_env.say(PARK, "deal")
    await comment_env.say(PARK, "a1", action_id=comment_env.action.id)
    await comment_env.say(BOSS, "a2", action_id=comment_env.action.id)
    await comment_env.say(KIM, "owner-read")
    # given: E에는 PARK의 읽지 않은 Comment 1건, Comment 없는 Deal F
    other_code, _ = await comment_env.other_deal()
    await comment_env.say(PARK, "e", code=other_code)
    quiet = (await comment_env.actions.env.new_deal()).item.deal.id.value

    # when: 조건 없이 목록을 읽는다
    counts = await _counts(comment_env)

    # then: D 3, E 1, F 0이고 D의 값은 comment-counts의 unread(total)와 같다
    assert counts[comment_env.code] == 3
    assert counts[other_code] == 1
    assert counts[quiet] == 0
    assert counts[comment_env.code] == (await comment_env.counts.execute(comment_env.code)).total


async def test_the_row_value_follows_writes_reads_and_deletions_immediately(
    comment_env: CommentEnv,
) -> None:
    """작성·읽음 처리·Comment 삭제·Action 삭제가 다음 목록 조회의 값에 바로 반영된다.

    테스트 코드: CM-086
    """
    code = comment_env.code
    seen: list[int] = []

    # given: D에 Comment가 없다
    assert (await _counts(comment_env))[code] == 0

    # when: ① PARK ② KIM(Owner) ③ BOSS(Action Comment) 작성, ④ KIM 읽음 처리, ⑤ 삭제, ⑥ Action 삭제
    first = await comment_env.say(PARK, "one")
    seen.append((await _counts(comment_env))[code])
    await comment_env.say(KIM, "owner")
    seen.append((await _counts(comment_env))[code])
    await comment_env.say(BOSS, "action", action_id=comment_env.action.id)
    seen.append((await _counts(comment_env))[code])
    await comment_env.mark_read.execute(code, KIM, [first.id])
    seen.append((await _counts(comment_env))[code])
    await comment_env.delete.execute(first.id, PARK)
    seen.append((await _counts(comment_env))[code])
    await comment_env.actions.delete.execute(comment_env.action.id, KIM)
    seen.append((await _counts(comment_env))[code])

    # then: 1, 1, 2, 1, 1, 0이다
    assert seen == [1, 1, 2, 1, 1, 0]


async def test_unread_comments_do_not_change_the_page_order_or_total(
    comment_env: CommentEnv,
) -> None:
    """읽지 않은 수는 같은 조건·정렬의 행 순서와 total에 영향이 없고 그 행의 값만 바뀐다.

    테스트 코드: CM-088
    """
    # given: Deal 3건(D 포함)
    await comment_env.actions.env.new_deal()
    await comment_env.actions.env.new_deal()
    query = DealQuery(sort=DealSort.NAME, limit=200)
    before = await comment_env.actions.env.list.execute(query)

    # when: D에 읽지 않은 Comment 3건을 쓰고 같은 조건으로 다시 조회한다
    for n in range(3):
        await comment_env.say(PARK, f"c{n}")
    after = await comment_env.actions.env.list.execute(query)

    # then: 행 순서·total은 같고 D 행 값만 0에서 3으로 바뀐다
    assert [v.item.deal.id for v in after.items] == [v.item.deal.id for v in before.items]
    assert after.total == before.total == 3
    assert {v.item.deal.id.value: v.item.unread_comment_count for v in before.items}[
        comment_env.code
    ] == 0
    assert {v.item.deal.id.value: v.item.unread_comment_count for v in after.items}[
        comment_env.code
    ] == 3
    assert sum(v.item.unread_comment_count for v in after.items) == 3
