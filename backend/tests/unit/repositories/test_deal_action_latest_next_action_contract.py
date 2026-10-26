"""DealActionRepository.latest_with_next_action 계약(R4 AC4-1): Fake와 SQL에 같은 기대값.

기준 행 = 그 Deal에서 Next Action이 있는 가장 최근 Action(수행일시 내림차순, 같으면 id 내림차순).
Deal 목록·상세의 `next_action`이 가리키는 행과 같은 정의여야 한다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.domain.deal_action.value_objects import DealActionId
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"
OTHER = "20261016-A002"


async def test_latest_with_next_action_skips_actions_without_next_action(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    earlier = await deal_case.add_action(deal, acted_at=later(100), next_action="견적 회신")
    await deal_case.add_action(deal, acted_at=later(200), action="통화만", next_action="")

    found = await deal_case.actions.latest_with_next_action(deal.id)

    assert found is not None
    assert found.id == earlier.id
    assert found.content.next_action == "견적 회신"


async def test_latest_with_next_action_picks_the_most_recent_acted_at(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="첫째")
    newest = await deal_case.add_action(deal, acted_at=later(300), next_action="셋째")
    await deal_case.add_action(deal, acted_at=later(200), next_action="둘째")

    found = await deal_case.actions.latest_with_next_action(deal.id)

    assert found is not None
    assert found.id == newest.id


async def test_latest_with_next_action_breaks_ties_by_higher_id(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    low = await deal_case.add_action(
        deal, acted_at=later(100), entity_id=DealActionId(2_000_000_001), next_action="낮은 id"
    )
    high = await deal_case.add_action(
        deal, acted_at=later(100), entity_id=DealActionId(2_000_000_009), next_action="높은 id"
    )

    found = await deal_case.actions.latest_with_next_action(deal.id)

    assert found is not None
    assert found.id == high.id
    assert found.id != low.id


async def test_latest_with_next_action_is_none_without_next_actions(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    assert await deal_case.actions.latest_with_next_action(deal.id) is None

    await deal_case.add_action(deal, acted_at=later(100), action="통화만", next_action="")

    assert await deal_case.actions.latest_with_next_action(deal.id) is None


async def test_latest_with_next_action_includes_closed_rows(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="먼저")
    closed = await deal_case.add_action(deal, acted_at=later(200), next_action="나중")
    await deal_case.set_next_action_status(closed, "done", later(300))

    found = await deal_case.actions.latest_with_next_action(deal.id)

    assert found is not None
    assert found.id == closed.id
    assert found.next_action_state is not None
    assert found.next_action_state.status.value == "done"


async def test_latest_with_next_action_only_looks_at_the_given_deal(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    other = make_deal(later(5), code=OTHER)
    await deal_case.add(deal)
    await deal_case.add(other)
    mine = await deal_case.add_action(deal, acted_at=later(100), next_action="내 것")
    await deal_case.add_action(other, acted_at=later(500), next_action="남의 것")

    found = await deal_case.actions.latest_with_next_action(deal.id)

    assert found is not None
    assert found.id == mine.id


async def test_latest_with_next_action_returns_the_full_action_like_get(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    added = await deal_case.add_action(
        deal, acted_at=later(100), next_action="견적 회신", due_date=date(2026, 2, 3), memo="메모"
    )

    found = await deal_case.actions.latest_with_next_action(deal.id)

    assert found is not None
    stored = await deal_case.actions.get(added.id)
    assert found.content == stored.content
    assert found.next_action_state == stored.next_action_state
    assert found.actor_user_id == stored.actor_user_id
    assert found.acted_at == stored.acted_at
    assert found.deal_code == deal.id


async def test_latest_with_next_action_matches_deal_list_basis(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(
        deal, acted_at=later(100), next_action="첫째", due_date=date(2026, 3, 1)
    )
    await deal_case.add_action(
        deal, acted_at=later(200), next_action="둘째", due_date=date(2026, 3, 2)
    )
    await deal_case.add_action(
        deal, acted_at=later(200), next_action="셋째", due_date=date(2026, 3, 3)
    )
    await deal_case.add_action(deal, acted_at=later(400), action="통화만", next_action="")

    found = await deal_case.actions.latest_with_next_action(deal.id)
    summary = (await deal_case.deals.get_item(deal.id)).next_action

    assert found is not None
    assert summary is not None
    assert (found.content.next_action, found.content.due_date) == (summary.text, summary.due_date)
