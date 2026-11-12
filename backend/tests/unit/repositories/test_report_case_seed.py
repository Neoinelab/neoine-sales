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
    """준비 도우미는 Deal·Action을 저장하고 Action 유형 id를 찾는다."""
    # given: Vendor SAP의 Deal 하나와 미팅 Action
    case = ReportCase(deal_case, None, None)  # type: ignore[arg-type]
    sap = await deal_case.new_vendor("SAP")
    deal = await case.add_deal(name="A", vendor_id=sap.id, amount=7, day=date(2026, 4, 1))
    await deal_case.add_action(deal, kst(2026, 10, 5), action_type="미팅", action="x")
    meeting = await case.type_id("미팅")

    # when: Deal 목록과 Deal의 Action을 읽는다
    found = await deal_case.deals.search(DealQuery(limit=10))
    actions = await deal_case.actions_of(deal.id)

    # then: Deal 하나, Action 유형은 미팅 id, 수행일시가 준 값이다
    assert [item.deal.id for item in found] == [deal.id]
    assert [a.content.action_type.id for a in actions] == [meeting]
    assert actions[0].acted_at == kst(2026, 10, 5)


async def test_seed_helper_codes_are_unique_and_ordered(deal_case: DealCase) -> None:
    """준비 도우미가 만드는 Deal code는 등록 순서대로 커진다."""
    # given: Deal 둘을 차례로 등록
    case = ReportCase(deal_case, None, None)  # type: ignore[arg-type]

    # when: 두 Deal을 만든다
    first = await case.add_deal()
    second = await case.add_deal()

    # then: 첫째 code가 둘째보다 앞선다
    assert first.id.value < second.id.value
