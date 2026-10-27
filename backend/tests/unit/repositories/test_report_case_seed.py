"""Reports 계약 테스트의 준비 도우미(`ReportCase`)가 만드는 데이터가 기대와 같은지 확인한다.

리포트 구현과 무관하게 Deal·Action·Vendor·사용자가 저장되고 읽히는지(계약 테스트의 전제)를 본다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from tests.unit.repositories.report_case import ReportCase, kst

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


async def test_seed_helpers_store_deals_actions_and_resolve_type_ids(deal_case: DealCase) -> None:
    case = ReportCase(deal_case, None, None)  # type: ignore[arg-type]
    sap = await deal_case.new_vendor("SAP")
    deal = await case.add_deal(name="A", vendor_id=sap.id, amount=7, day=date(2026, 4, 1))
    await deal_case.add_action(deal, kst(2026, 10, 5), action_type="미팅", action="x")
    meeting = await case.type_id("미팅")

    found = await deal_case.deals.search(DealQuery(limit=10))
    actions = await deal_case.actions_of(deal.id)

    assert [item.deal.id for item in found] == [deal.id]
    assert [a.content.action_type.id for a in actions] == [meeting]
    assert actions[0].acted_at == kst(2026, 10, 5)


async def test_seed_helper_codes_are_unique_and_ordered(deal_case: DealCase) -> None:
    case = ReportCase(deal_case, None, None)  # type: ignore[arg-type]

    first = await case.add_deal()
    second = await case.add_deal()

    assert first.id.value < second.id.value
