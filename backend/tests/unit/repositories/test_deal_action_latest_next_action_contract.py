"""DealActionRepository.latest_with_next_action 계약: Fake와 SQL에 같은 기대값.

기준 행 = 그 Deal에서 Next Action이 있는 가장 최근 Action(수행일 내림차순, 같으면 id 내림차순).
Deal 목록·상세의 `next_action`이 가리키는 행과 같은 정의여야 한다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.domain.deal_action.value_objects import DealActionId
from tests.factories import date_after, later, make_deal

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"
OTHER = "20261016-A002"


async def test_latest_with_next_action_skips_actions_without_next_action(
    deal_case: DealCase,
) -> None:
    """Next Action이 없는 Action은 건너뛰고 Next Action이 있는 Action을 돌려준다."""
    # given: Next Action이 있는 Action과, 더 최근이지만 Next Action이 없는 Action을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    earlier = await deal_case.add_action(deal, acted_on=date_after(1), next_action="견적 회신")
    await deal_case.add_action(deal, acted_on=date_after(2), action="통화만", next_action="")

    # when: Deal의 Next Action 기준 Action을 조회한다
    found = await deal_case.actions.latest_with_next_action(deal.id)

    # then: Next Action이 있는 쪽 Action이다
    assert found is not None
    assert found.id == earlier.id
    assert found.content.next_action == "견적 회신"


async def test_latest_with_next_action_picks_the_most_recent_acted_on(
    deal_case: DealCase,
) -> None:
    """Next Action이 있는 Action 중 수행일이 가장 최근인 것을 돌려준다.

    테스트 코드: AC-115
    """
    # given: 수행일이 다른 Next Action 3건을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_on=date_after(1), next_action="첫째")
    newest = await deal_case.add_action(deal, acted_on=date_after(3), next_action="셋째")
    await deal_case.add_action(deal, acted_on=date_after(2), next_action="둘째")

    # when: Deal의 Next Action 기준 Action을 조회한다
    found = await deal_case.actions.latest_with_next_action(deal.id)

    # then: 수행일이 가장 최근인 Action이다
    assert found is not None
    assert found.id == newest.id


async def test_latest_with_next_action_breaks_ties_by_higher_id(deal_case: DealCase) -> None:
    """수행일이 같으면 id가 큰 Action을 돌려준다.

    테스트 코드: AC-115
    """
    # given: 수행일이 같고 id가 다른 Next Action 2건을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    low = await deal_case.add_action(
        deal, acted_on=date_after(1), entity_id=DealActionId(2_000_000_001), next_action="낮은 id"
    )
    high = await deal_case.add_action(
        deal, acted_on=date_after(1), entity_id=DealActionId(2_000_000_009), next_action="높은 id"
    )

    # when: Deal의 Next Action 기준 Action을 조회한다
    found = await deal_case.actions.latest_with_next_action(deal.id)

    # then: id가 큰 쪽이다
    assert found is not None
    assert found.id == high.id
    assert found.id != low.id


async def test_latest_with_next_action_is_none_without_next_actions(
    deal_case: DealCase,
) -> None:
    """Next Action이 있는 Action이 없으면 None이다."""
    # given: Action이 하나도 없는 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    # when: 기준 Action을 조회한다
    empty = await deal_case.actions.latest_with_next_action(deal.id)
    # then: None이다
    assert empty is None

    # given: Next Action이 없는 Action만 있는 Deal
    await deal_case.add_action(deal, acted_on=date_after(1), action="통화만", next_action="")

    # when: 기준 Action을 조회한다
    without_next = await deal_case.actions.latest_with_next_action(deal.id)
    # then: 여전히 None이다
    assert without_next is None


async def test_latest_with_next_action_includes_closed_rows(deal_case: DealCase) -> None:
    """이미 종료(수행)한 Next Action도 기준 Action이 될 수 있다."""
    # given: 가장 최근 Next Action을 수행 종료한 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_on=date_after(1), next_action="먼저")
    closed = await deal_case.add_action(deal, acted_on=date_after(2), next_action="나중")
    await deal_case.set_next_action_status(closed, "done", later(300))

    # when: Deal의 Next Action 기준 Action을 조회한다
    found = await deal_case.actions.latest_with_next_action(deal.id)

    # then: 종료된 그 Action이고 상태는 done이다
    assert found is not None
    assert found.id == closed.id
    assert found.next_action_state is not None
    assert found.next_action_state.status.value == "done"


async def test_latest_with_next_action_only_looks_at_the_given_deal(
    deal_case: DealCase,
) -> None:
    """다른 Deal의 Action은 보지 않고 지정한 Deal의 Action만 돌려준다."""
    # given: 각자 Next Action이 있는 두 Deal(다른 Deal 쪽이 더 최근)
    deal = make_deal(later(5), code=CODE)
    other = make_deal(later(5), code=OTHER)
    await deal_case.add(deal)
    await deal_case.add(other)
    mine = await deal_case.add_action(deal, acted_on=date_after(1), next_action="내 것")
    await deal_case.add_action(other, acted_on=date_after(5), next_action="남의 것")

    # when: Deal의 Next Action 기준 Action을 조회한다
    found = await deal_case.actions.latest_with_next_action(deal.id)

    # then: 지정한 Deal의 Action이다
    assert found is not None
    assert found.id == mine.id


async def test_latest_with_next_action_returns_the_full_action_like_get(
    deal_case: DealCase,
) -> None:
    """돌려주는 Action은 get으로 읽은 것과 모든 필드가 같다."""
    # given: 기한·Memo까지 채운 Next Action이 있는 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    added = await deal_case.add_action(
        deal,
        acted_on=date_after(1),
        next_action="견적 회신",
        due_date=date(2026, 2, 3),
        memo="메모",
    )

    # when: Deal의 Next Action 기준 Action을 조회한다
    found = await deal_case.actions.latest_with_next_action(deal.id)

    # then: get으로 읽은 Action과 내용·상태·수행자·수행일·Deal이 같다
    assert found is not None
    stored = await deal_case.actions.get(added.id)
    assert found.content == stored.content
    assert found.next_action_state == stored.next_action_state
    assert found.actor_user_id == stored.actor_user_id
    assert found.acted_on == stored.acted_on
    assert found.deal_code == deal.id


async def test_latest_with_next_action_matches_deal_list_basis(deal_case: DealCase) -> None:
    """Action 기준 조회는 Deal 목록의 Next Action 요약과 같은 행을 가리킨다."""
    # given: Next Action이 여러 개이고 마지막에 Next Action 없는 Action이 있는 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(
        deal, acted_on=date_after(1), next_action="첫째", due_date=date(2026, 3, 1)
    )
    await deal_case.add_action(
        deal, acted_on=date_after(2), next_action="둘째", due_date=date(2026, 3, 2)
    )
    await deal_case.add_action(
        deal, acted_on=date_after(2), next_action="셋째", due_date=date(2026, 3, 3)
    )
    await deal_case.add_action(deal, acted_on=date_after(4), action="통화만", next_action="")

    # when: Deal의 Next Action 기준 Action을 조회한다
    found = await deal_case.actions.latest_with_next_action(deal.id)
    # when: Deal 목록 항목의 Next Action 요약을 읽는다
    summary = (await deal_case.deals.get_item(deal.id)).next_action

    # then: 두 곳의 Next Action 문구와 기한이 같다
    assert found is not None
    assert summary is not None
    assert (found.content.next_action, found.content.due_date) == (summary.text, summary.due_date)
