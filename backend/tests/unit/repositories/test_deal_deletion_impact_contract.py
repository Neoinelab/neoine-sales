"""DealRepository.deletion_impact 계약(R3, AC-26): 지우면 함께 사라지는 이력·활동 건수.

Fake와 SQL(PostgreSQL)에 같은 기대값. 첨부 파일은 P2b 전이라 attachment_count는 항상 0이다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.history import DealHistoryEntry, HistoryCategory, HistoryDraft
from tests.factories import later, make_deal
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"
OTHER = "20261016-A002"


def _entry(code: str, at: int) -> DealHistoryEntry:
    draft = HistoryDraft(HistoryCategory.OTHER, "Deal Name", "A", "B")
    return DealHistoryEntry(None, make_deal(code=code).id, later(at), OWNER_ID, draft)


async def test_a_deal_without_history_or_actions_has_zero_counts(deal_case: DealCase) -> None:
    await deal_case.add(make_deal(code=CODE))

    impact = await deal_case.deals.deletion_impact(make_deal(code=CODE).id)

    assert impact == DealDeletionImpact(
        history_count=0, action_count=0, attachment_count=0, partner_meeting_count=0
    )


async def test_history_and_actions_are_counted_per_kind(deal_case: DealCase) -> None:
    deal = make_deal(code=CODE)
    await deal_case.add(deal)
    await deal_case.history.add_many([_entry(CODE, 1), _entry(CODE, 2), _entry(CODE, 3)])
    await deal_case.add_action(deal, acted_at=later(10))
    await deal_case.add_action(deal, acted_at=later(20))

    impact = await deal_case.deals.deletion_impact(deal.id)

    assert impact == DealDeletionImpact(
        history_count=3, action_count=2, attachment_count=0, partner_meeting_count=0
    )


async def test_other_deals_are_not_counted(deal_case: DealCase) -> None:
    first, second = make_deal(code=CODE), make_deal(code=OTHER)
    await deal_case.add(first)
    await deal_case.add(second)
    await deal_case.history.add_many([_entry(CODE, 1), _entry(OTHER, 2), _entry(OTHER, 3)])
    await deal_case.add_action(second, acted_at=later(10))

    impact = await deal_case.deals.deletion_impact(first.id)

    assert impact == DealDeletionImpact(
        history_count=1, action_count=0, attachment_count=0, partner_meeting_count=0
    )


async def test_the_counts_are_what_a_delete_would_remove(deal_case: DealCase) -> None:
    deal = make_deal(code=CODE)
    await deal_case.add(deal)
    await deal_case.history.add_many([_entry(CODE, 1), _entry(CODE, 2)])
    await deal_case.add_action(deal, acted_at=later(10))
    impact = await deal_case.deals.deletion_impact(deal.id)

    await deal_case.deals.delete(deal.id)

    assert list(await deal_case.history.list(deal.id)) == []
    assert await deal_case.actions_of(deal.id) == []
    assert (impact.history_count, impact.action_count) == (2, 1)


async def test_an_unknown_deal_is_not_found(deal_case: DealCase) -> None:
    with pytest.raises(DealNotFoundError):
        await deal_case.deals.deletion_impact(make_deal(code=CODE).id)
