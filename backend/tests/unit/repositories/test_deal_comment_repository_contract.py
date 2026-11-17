"""DealCommentRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트.

저장·읽기·읽음 처리·읽지 않은 수·삭제(수정은 없다), 최근순 목록·필터, 참조 오류(같은 Deal의
Action만 연결), Action·Deal 삭제 때의
CASCADE. 실패하는 호출은 테스트마다 마지막 하나뿐이다(SQL 트랜잭션).
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.value_objects import DealActionId
from app.domain.deal_comment.errors import DealCommentNotFoundError
from tests.factories import NOW, later, make_deal
from tests.factories_comment import make_comment
from tests.support.ids import MAX_ID, MISSING_ID
from tests.support.user_ids import ACTOR_ID, uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"
OTHER = "20261016-A002"
OTHER_EMPTY = "20261016-A009"  # 저장하지 않은 Deal(Comment 없음)


async def _deal(deal_case: DealCase, code: str = CODE) -> Deal:
    deal = make_deal(code=code)
    await deal_case.add(deal)
    return deal


async def test_add_and_get_round_trip_keeps_every_field(deal_case: DealCase) -> None:
    """저장한 Comment를 읽으면 모든 필드가 그대로다(Action Comment).

    테스트 코드: CM-001, CM-008
    """
    # given: Action이 있는 Deal과 그 Action에 연결한 Comment
    deal = await _deal(deal_case)
    action = await deal_case.add_action(deal)
    comment = make_comment(
        deal_code=deal.id,
        action_id=action.id,
        body="자료 전달\n둘째 줄",
        author=uid("kim"),
        now=NOW,
    )
    await ensure_users(deal_case.users, comment.author_user_id)
    await deal_case.comments.add(comment)

    # when: 저장한 Comment를 읽는다
    stored = await deal_case.comments.get(comment.id)

    # then: 필드가 모두 그대로다
    assert stored.id == comment.id
    assert stored.deal_code == deal.id
    assert stored.action_id == action.id
    assert stored.author_user_id == uid("kim")
    assert stored.body == "자료 전달\n둘째 줄"
    assert stored.created_at == stored.updated_at == NOW
    assert stored.read_at is None  # Owner가 쓴 것이 아니므로 읽지 않음


async def test_read_at_round_trips_for_read_and_unread_comments(deal_case: DealCase) -> None:
    """읽음(read_at = 작성 시각)과 읽지 않음(None)이 저장·읽기에서 그대로다.

    테스트 코드: CM-048, CM-049
    """
    # given: 읽음으로 만든 Comment와 읽지 않은 Comment
    deal = await _deal(deal_case)
    read = await deal_case.add_comment(deal.id, "read", later(1), read=True)
    unread = await deal_case.add_comment(deal.id, "unread", later(2))

    # when: 읽는다
    stored_read = await deal_case.comments.get(read.id)
    stored_unread = await deal_case.comments.get(unread.id)

    # then: 읽음은 작성 시각, 읽지 않음은 None이다
    assert stored_read.read_at == later(1)
    assert stored_unread.read_at is None


async def test_a_deal_comment_round_trips_with_a_null_action(deal_case: DealCase) -> None:
    """연결 Action이 없는 Deal Comment는 action_id가 None으로 돌아온다.

    테스트 코드: CM-001
    """
    # given: Deal Comment
    deal = await _deal(deal_case)
    comment = await deal_case.add_comment(deal.id, "예산 확인")

    # when: 읽는다
    stored = await deal_case.comments.get(comment.id)

    # then: 연결 Action이 없다
    assert stored.action_id is None
    assert stored.deal_code == deal.id


async def test_a_very_long_body_is_stored_without_truncation(deal_case: DealCase) -> None:
    """20,000자 본문도 잘리지 않고 저장된다(길이 상한 없음).

    테스트 코드: CM-002
    """
    # given: 20,000자 본문의 Comment
    deal = await _deal(deal_case)
    comment = await deal_case.add_comment(deal.id, "가" * 20_000)

    # when: 읽는다
    stored = await deal_case.comments.get(comment.id)

    # then: 그대로다
    assert stored.body == "가" * 20_000


async def test_list_returns_the_deals_comments_newest_first_with_id_as_tiebreaker(
    deal_case: DealCase,
) -> None:
    """목록은 그 Deal 소속 Comment 전부를 최근순(created_at·id 내림차순)으로 주고 다른 Deal 건 뺀다.

    테스트 코드: CM-013
    """
    # given: D에 T1 Deal Comment c1, T2 Action Comment c2, 같은 T2 Deal Comment c3(더 큰 id), E에 c4
    deal = await _deal(deal_case)
    other = await _deal(deal_case, OTHER)
    action = await deal_case.add_action(deal)
    c3 = make_comment(deal_code=deal.id, body="c3", now=later(20), entity_id=MAX_ID - 10)
    c2 = make_comment(
        deal_code=deal.id, action_id=action.id, body="c2", now=later(20), entity_id=MAX_ID - 20
    )
    await ensure_users(deal_case.users, ACTOR_ID)
    await deal_case.comments.add(c2)  # 일부러 id가 작은 것을 먼저 저장한다
    await deal_case.comments.add(c3)
    await deal_case.add_comment(deal.id, "c1", later(10))
    await deal_case.add_comment(other.id, "c4", later(5))

    # when: D의 목록을 읽는다
    found = await deal_case.comments.list_for_deal(deal.id)

    # then: c3, c2, c1 순서이고 c4는 없다(같은 시각에서는 id가 큰 c3이 먼저)
    assert [c.body for c in found] == ["c3", "c2", "c1"]
    assert [c.action_id for c in found] == [None, action.id, None]


async def test_list_filtered_by_action_returns_only_that_actions_comments(
    deal_case: DealCase,
) -> None:
    """action_id로 거르면 그 Action의 Comment만 나오고 그 Deal에 없는 Action id는 0건이다.

    테스트 코드: CM-014
    """
    # given: Deal에 Action 둘, 각 Action의 Comment와 Deal Comment
    deal = await _deal(deal_case)
    first = await deal_case.add_action(deal)
    second = await deal_case.add_action(deal)
    await deal_case.add_comment(deal.id, "deal", later(1))
    await deal_case.add_comment(deal.id, "first", later(2), action=first)
    await deal_case.add_comment(deal.id, "second", later(3), action=second)

    # when: 각 조건으로 읽는다
    of_first = await deal_case.comments.list_for_deal(deal.id, action_id=first.id)
    of_missing = await deal_case.comments.list_for_deal(deal.id, action_id=MISSING_ID)

    # then: 그 Action의 Comment만 나오고 없는 id는 빈 목록이다
    assert [c.body for c in of_first] == ["first"]
    assert list(of_missing) == []


async def test_get_of_a_missing_comment_raises_not_found(deal_case: DealCase) -> None:
    """없는 Comment를 읽으면 DealCommentNotFoundError다.

    테스트 코드: CM-016
    """
    # when·then: 없는 id(상한값 포함)는 NotFound다
    with pytest.raises(DealCommentNotFoundError):
        await deal_case.comments.get(MAX_ID)


async def test_mark_read_fills_only_unread_comments_of_that_deal(deal_case: DealCase) -> None:
    """mark_read는 그 Deal 소속이면서 읽지 않은 행만 채우고 다른 Deal·없는·이미 읽은 id는 건너뛴다.

    테스트 코드: CM-049, CM-051
    """
    # given: D에 읽지 않은 c1·c2와 이미 읽은 c3(읽은 시각 R1), E에 읽지 않은 e1
    deal = await _deal(deal_case)
    other = await _deal(deal_case, OTHER)
    c1 = await deal_case.add_comment(deal.id, "c1", later(1))
    c2 = await deal_case.add_comment(deal.id, "c2", later(2))
    c3 = await deal_case.add_comment(deal.id, "c3", later(3), read=True)
    e1 = await deal_case.add_comment(other.id, "e1", later(4))

    # when: [c1, c1, c3, e1, 없는 id]를 later(100)에 읽음 처리한다(c2는 대상이 아니다)
    await deal_case.comments.mark_read(deal.id, [c1.id, c1.id, c3.id, e1.id, MAX_ID], later(100))

    # then: c1만 채워지고 c3는 그대로, c2·e1은 읽지 않음 그대로다
    assert (await deal_case.comments.get(c1.id)).read_at == later(100)
    assert (await deal_case.comments.get(c3.id)).read_at == later(3)
    assert (await deal_case.comments.get(c2.id)).read_at is None
    assert (await deal_case.comments.get(e1.id)).read_at is None


async def test_mark_read_changes_only_read_at(deal_case: DealCase) -> None:
    """읽음 처리는 본문·수정 시각·연결 Action·작성자를 바꾸지 않는다.

    테스트 코드: CM-054
    """
    # given: 읽지 않은 Action Comment
    deal = await _deal(deal_case)
    action = await deal_case.add_action(deal)
    comment = await deal_case.add_comment(deal.id, "자료 전달", NOW, action=action)

    # when: 읽음 처리한다
    await deal_case.comments.mark_read(deal.id, [comment.id], later(60))
    stored = await deal_case.comments.get(comment.id)

    # then: read_at만 바뀐다
    assert stored.read_at == later(60)
    assert (stored.body, stored.updated_at, stored.created_at) == ("자료 전달", NOW, NOW)
    assert (stored.action_id, stored.author_user_id, stored.deal_code) == (
        action.id,
        ACTOR_ID,
        deal.id,
    )


async def test_unread_counts_gives_the_deal_total_and_actions_with_one_or_more(
    deal_case: DealCase,
) -> None:
    """unread_counts는 읽지 않은 행을 Deal 전체와 Action별(1 이상만)로 세고 다른 Deal 것은 뺀다.

    테스트 코드: CM-055
    """
    # given: D에 읽지 않은 Deal Comment 1건, A의 읽지 않은 2건, B의 읽은 1건, E에 읽지 않은 3건
    deal = await _deal(deal_case)
    other = await _deal(deal_case, OTHER)
    first = await deal_case.add_action(deal)
    second = await deal_case.add_action(deal)
    foreign = await deal_case.add_action(other)
    await deal_case.add_comment(deal.id, "d", later(1))
    await deal_case.add_comment(deal.id, "a1", later(2), action=first)
    await deal_case.add_comment(deal.id, "a2", later(3), action=first)
    await deal_case.add_comment(deal.id, "b", later(4), action=second, read=True)
    await deal_case.add_comment(other.id, "e1", later(5))
    await deal_case.add_comment(other.id, "e2", later(6), action=foreign)
    await deal_case.add_comment(other.id, "e3", later(7), action=foreign)

    # when: 센다
    counts = await deal_case.comments.unread_counts(deal.id)
    none_left = await deal_case.comments.unread_counts(DealCode(OTHER_EMPTY))

    # then: 전체 3, A만 2다. 소속 Comment가 없는 Deal은 0·빈 맵이다
    assert counts.total == 3
    assert dict(counts.by_action) == {first.id: 2}
    assert (none_left.total, dict(none_left.by_action)) == (0, {})


async def test_delete_removes_the_row_and_a_second_delete_raises_not_found(
    deal_case: DealCase,
) -> None:
    """삭제하면 행이 없어지고 다시 지우면 NotFound다.

    테스트 코드: CM-024
    """
    # given: 저장된 Comment
    deal = await _deal(deal_case)
    comment = await deal_case.add_comment(deal.id)

    # when: 지운다
    await deal_case.comments.delete(comment.id)

    # then: 목록에서 사라지고 다시 지우면 NotFound다
    assert list(await deal_case.comments.list_for_deal(deal.id)) == []
    with pytest.raises(DealCommentNotFoundError):
        await deal_case.comments.delete(comment.id)


async def test_add_with_an_existing_id_raises_already_exists(deal_case: DealCase) -> None:
    """같은 id의 Comment를 다시 저장하면 이미 존재 오류가 난다."""
    # given: 저장된 Comment
    deal = await _deal(deal_case)
    comment = await deal_case.add_comment(deal.id)

    # when·then: 같은 id로 다시 저장하면 AlreadyExistsError다
    with pytest.raises(AlreadyExistsError):
        await deal_case.comments.add(make_comment(deal_code=deal.id, entity_id=int(comment.id)))


async def test_add_to_a_missing_deal_raises_deal_not_found(deal_case: DealCase) -> None:
    """없는 Deal에 저장하면 DealNotFoundError다(모든 Comment는 Deal이 있다).

    테스트 코드: CM-006, CM-045
    """
    # given: 저장되지 않은 Deal 소속 Comment와 그 작성자
    await ensure_users(deal_case.users, ACTOR_ID)
    comment = make_comment(deal_code=make_deal(code=OTHER).id)

    # when·then: 저장하면 DealNotFoundError다
    with pytest.raises(DealNotFoundError):
        await deal_case.comments.add(comment)


async def test_add_with_another_deals_action_raises_invalid_reference(
    deal_case: DealCase,
) -> None:
    """다른 Deal의 Action을 연결하면 InvalidReferenceError다(복합 FK).

    테스트 코드: CM-009, CM-045
    """
    # given: D와 E, E의 Action B
    deal = await _deal(deal_case)
    other = await _deal(deal_case, OTHER)
    foreign = await deal_case.add_action(other)
    await ensure_users(deal_case.users, ACTOR_ID)

    # when·then: D의 Comment로 B를 연결하면 InvalidReferenceError("Action")이다
    with pytest.raises(InvalidReferenceError) as caught:
        await deal_case.comments.add(make_comment(deal_code=deal.id, action_id=foreign.id))
    assert caught.value.entity == "Action"


async def test_add_with_a_missing_action_raises_invalid_reference(deal_case: DealCase) -> None:
    """없는 Action을 연결하면 InvalidReferenceError다.

    테스트 코드: CM-009
    """
    # given: Deal과 작성자
    deal = await _deal(deal_case)
    await ensure_users(deal_case.users, ACTOR_ID)

    # when·then: 없는 Action id를 연결하면 InvalidReferenceError("Action")이다
    with pytest.raises(InvalidReferenceError) as caught:
        await deal_case.comments.add(
            make_comment(deal_code=deal.id, action_id=DealActionId(MISSING_ID))
        )
    assert caught.value.entity == "Action"


async def test_add_with_a_missing_author_raises_invalid_reference(deal_case: DealCase) -> None:
    """없는 작성자를 쓰면 InvalidReferenceError("사용자")다.

    테스트 코드: CM-045
    """
    # given: Deal만 있고 작성자 행은 없다
    deal = await _deal(deal_case)

    # when·then: 없는 작성자의 Comment를 저장하면 InvalidReferenceError("사용자")다
    with pytest.raises(InvalidReferenceError) as caught:
        await deal_case.comments.add(make_comment(deal_code=deal.id, author=uid("nobody")))
    assert caught.value.entity == "사용자"


async def test_count_for_action_counts_only_that_actions_comments(deal_case: DealCase) -> None:
    """count_for_action은 그 Action에 연결된 Comment 수만 센다.

    테스트 코드: CM-037
    """
    # given: Action 두 개와 Comment(첫째 Action 2건, 둘째 1건, Deal Comment 1건)
    deal = await _deal(deal_case)
    first = await deal_case.add_action(deal)
    second = await deal_case.add_action(deal)
    await deal_case.add_comment(deal.id, "a", later(1), action=first)
    await deal_case.add_comment(deal.id, "b", later(2), action=first)
    await deal_case.add_comment(deal.id, "c", later(3), action=second)
    await deal_case.add_comment(deal.id, "d", later(4))

    # when: 각 Action의 Comment 수를 읽는다
    counts = (
        await deal_case.comments.count_for_action(first.id),
        await deal_case.comments.count_for_action(second.id),
        await deal_case.comments.count_for_action(MISSING_ID),
    )

    # then: 2, 1, 0이다
    assert counts == (2, 1, 0)


async def test_deleting_an_action_removes_only_its_comments(deal_case: DealCase) -> None:
    """Action을 지우면 그 Action Comment만 함께 지워지고 Deal Comment·다른 Action의 것은 남는다.

    테스트 코드: CM-037, CM-045
    """
    # given: A에 Comment 2건, Deal Comment 1건, 다른 Action A2에 Comment 1건
    deal = await _deal(deal_case)
    first = await deal_case.add_action(deal)
    second = await deal_case.add_action(deal)
    await deal_case.add_comment(deal.id, "a1", later(1), action=first)
    await deal_case.add_comment(deal.id, "a2", later(2), action=first)
    await deal_case.add_comment(deal.id, "deal", later(3))
    await deal_case.add_comment(deal.id, "b1", later(4), action=second)

    # when: A를 지운다
    await deal_case.actions.delete(first.id)

    # then: A의 Comment 2건만 사라진다
    remaining = await deal_case.comments.list_for_deal(deal.id)
    assert [c.body for c in remaining] == ["b1", "deal"]  # 최근순


async def test_deleting_a_deal_removes_all_of_its_comments_only(deal_case: DealCase) -> None:
    """Deal을 지우면 그 Deal 소속 Comment가 모두 지워지고 다른 Deal의 것은 남는다.

    테스트 코드: CM-039, CM-045
    """
    # given: D에 Deal Comment 1건·Action Comment 2건, E에 Comment 1건
    deal = await _deal(deal_case)
    other = await _deal(deal_case, OTHER)
    action = await deal_case.add_action(deal)
    await deal_case.add_comment(deal.id, "d", later(1))
    await deal_case.add_comment(deal.id, "a1", later(2), action=action)
    await deal_case.add_comment(deal.id, "a2", later(3), action=action)
    kept = await deal_case.add_comment(other.id, "e", later(4))

    # when: D를 지운다
    await deal_case.deals.delete(deal.id)

    # then: E의 Comment만 남는다
    assert [c.id for c in await deal_case.comments.list_for_deal(other.id)] == [kept.id]
    assert list(await deal_case.comments.list_for_deal(deal.id)) == []
