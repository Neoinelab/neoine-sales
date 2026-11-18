"""DealRepository 계약: 목록 행·단건 `unread_comment_count`(CM-R47). Fake와 SQL에 같은 기대값.

그 Deal 소속(Deal·Action Comment 모두) read_at이 없는 Comment 수이고 다른 Deal 것은 섞이지 않는다.
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from app.domain.deal.code import DealCode
    from tests.unit.repositories.deal_case import DealCase


async def _row_counts(case: DealCase) -> dict[str, int]:
    found = await case.deals.search(DealQuery(limit=200))
    return {item.deal.id.value: item.unread_comment_count for item in found}


async def test_search_and_get_item_count_unread_comments_of_that_deal_only(
    deal_case: DealCase,
) -> None:
    """search·get_item은 그 Deal의 읽지 않은 Deal·Action Comment 수를 주고 없으면 0이다.

    테스트 코드: CM-085
    """
    # given: D(읽지 않음 Deal 1·Action 2, 읽음 1), E(읽지 않음 1), Comment 없는 F
    d, e, f = (make_deal(code=f"20261016-A00{n}") for n in (1, 2, 3))
    for deal in (d, e, f):
        await deal_case.add(deal)
    action = await deal_case.add_action(d)
    await deal_case.add_comment(d.id, "deal", later(1))
    await deal_case.add_comment(d.id, "a1", later(2), action=action)
    await deal_case.add_comment(d.id, "a2", later(3), action=action)
    await deal_case.add_comment(d.id, "read", later(4), read=True)
    await deal_case.add_comment(e.id, "e", later(5))

    # when: 목록과 단건으로 읽는다
    counts = await _row_counts(deal_case)
    single: DealCode = d.id
    item = await deal_case.deals.get_item(single)

    # then: D 3, E 1, F 0이고 단건 값도 3이다
    assert counts == {d.id.value: 3, e.id.value: 1, f.id.value: 0}
    assert item.unread_comment_count == 3


async def test_the_count_follows_read_marking_and_comment_and_action_deletion(
    deal_case: DealCase,
) -> None:
    """읽음 처리·Comment 삭제·Action 삭제(CASCADE)가 다음 조회의 값에 반영된다.

    테스트 코드: CM-086
    """
    # given: D에 Deal Comment 2건(c1·c2)과 Action Comment 1건
    deal = make_deal()
    await deal_case.add(deal)
    action = await deal_case.add_action(deal)
    c1 = await deal_case.add_comment(deal.id, "c1", later(1))
    c2 = await deal_case.add_comment(deal.id, "c2", later(2))
    await deal_case.add_comment(deal.id, "a", later(3), action=action)
    seen = [(await _row_counts(deal_case))[deal.id.value]]

    # when: c1 읽음 처리, c2 삭제, Action 삭제를 차례로 하고 매번 읽는다
    await deal_case.comments.mark_read(deal.id, [c1.id], later(10))
    seen.append((await _row_counts(deal_case))[deal.id.value])
    await deal_case.comments.delete(c2.id)
    seen.append((await _row_counts(deal_case))[deal.id.value])
    await deal_case.actions.delete(action.id)
    seen.append((await _row_counts(deal_case))[deal.id.value])

    # then: 3, 2, 1, 0이다
    assert seen == [3, 2, 1, 0]
