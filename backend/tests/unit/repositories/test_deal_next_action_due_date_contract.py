"""DealRepository 계약(P2 R1 Minor 1): 목록·상세의 next_action.due_date는 항상 date다.

Fake와 SQL(PostgreSQL)에 같은 기대값. `search`와 `get_item` 모두 같다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def test_search_items_carry_a_date_due_date(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), due_date=date(2026, 2, 5))

    items = await deal_case.deals.search(DealQuery())

    summary = items[0].next_action
    assert summary is not None
    assert type(summary.due_date) is date
    assert summary.due_date == date(2026, 2, 5)


async def test_detail_item_carries_a_date_due_date(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), due_date=date(2026, 3, 1))

    item = await deal_case.deals.get_item(deal.id)

    assert item.next_action is not None
    assert type(item.next_action.due_date) is date
    assert not isinstance(item.next_action.due_date, datetime)
