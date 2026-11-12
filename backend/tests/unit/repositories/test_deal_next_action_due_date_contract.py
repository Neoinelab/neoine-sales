"""DealRepository 계약: 목록·상세의 next_action.due_date는 항상 date다.

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
    """목록 항목의 Next Action 기한은 date 타입이다."""
    # given: 기한이 있는 Next Action을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), due_date=date(2026, 2, 5))

    # when: 목록을 검색한다
    items = await deal_case.deals.search(DealQuery())

    # then: 요약 기한이 date 타입이고 2026-02-05다
    summary = items[0].next_action
    assert summary is not None
    assert type(summary.due_date) is date
    assert summary.due_date == date(2026, 2, 5)


async def test_detail_item_carries_a_date_due_date(deal_case: DealCase) -> None:
    """상세 항목의 Next Action 기한은 date 타입이다."""
    # given: 기한이 있는 Next Action을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), due_date=date(2026, 3, 1))

    # when: 상세로 조회한다
    item = await deal_case.deals.get_item(deal.id)

    # then: 요약 기한이 date 타입(datetime 아님)이다
    assert item.next_action is not None
    assert type(item.next_action.due_date) is date
    assert not isinstance(item.next_action.due_date, datetime)
