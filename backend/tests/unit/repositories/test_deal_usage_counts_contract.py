"""DealRepository 사용 수 집계 계약(R2: Status, 연락처): Fake와 SQL 구현에 같은 테스트를 적용한다.

Status 사용 수는 `deals.status_key` 기준이다(0인 항목은 무시하고 비교한다). Forecast·BANT Label
사용 수와 삭제 FK 매핑은 R3 계약이다. 연락처 사용 수는 고객 + 파트너 링크(비활성 포함)를 Deal당
1건으로 센다.
"""

from typing import TYPE_CHECKING

from app.domain.contact.values import ContactKind
from tests.factories import NOW, later, make_deal, new_contact_id

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.unit.repositories.deal_case import DealCase


def _nonzero(counts: Mapping[str, int]) -> dict[str, int]:
    return {key: count for key, count in counts.items() if count}


class TestCountByStatus:
    async def test_an_empty_repository_has_no_counts(self, deal_case: DealCase) -> None:
        assert _nonzero(await deal_case.deals.count_by_status()) == {}

    async def test_deals_are_grouped_by_status_key(self, deal_case: DealCase) -> None:
        for n, (status, forecast) in enumerate(
            [
                ("prospecting", "pipeline"),
                ("prospecting", "best"),
                ("introduction", "pipeline"),
                ("contract_completed", "won"),
            ],
            start=1,
        ):
            await deal_case.add(
                make_deal(
                    later(n), code=f"20261016-A00{n}", status_key=status, forecast_key=forecast
                )
            )

        counts = await deal_case.deals.count_by_status()

        assert _nonzero(counts) == {"prospecting": 2, "introduction": 1, "contract_completed": 1}

    async def test_counts_follow_status_changes_and_deletions(self, deal_case: DealCase) -> None:
        moved = make_deal(later(1), code="20261016-A001")
        removed = make_deal(later(2), code="20261016-A002", status_key="introduction")
        await deal_case.add(moved)
        await deal_case.add(removed)

        await deal_case.revise(moved.id, sync=make_deal(status_key="price_negotiation").sync)
        await deal_case.deals.delete(removed.id)

        assert _nonzero(await deal_case.deals.count_by_status()) == {"price_negotiation": 1}


class TestCountByContacts:
    async def test_counts_customers_and_partners_and_zero_for_unused_contacts(
        self, deal_case: DealCase
    ) -> None:
        customer = await deal_case.new_contact()
        partner = await deal_case.new_contact(ContactKind.PARTNER)
        idle = await deal_case.new_contact(company="안쓰는곳", name="무명")
        await deal_case.add(
            make_deal(code="20261016-A001", customer_id=customer.id, partner_id=partner.id)
        )
        await deal_case.add(make_deal(code="20261016-A002", customer_id=customer.id))

        counts = await deal_case.deals.count_by_contacts([customer.id, partner.id, idle.id])

        assert dict(counts) == {customer.id: 2, partner.id: 1, idle.id: 0}

    async def test_an_unknown_contact_is_zero_and_empty_input_is_empty(
        self, deal_case: DealCase
    ) -> None:
        unknown = new_contact_id()

        assert dict(await deal_case.deals.count_by_contacts([unknown])) == {unknown: 0}
        assert dict(await deal_case.deals.count_by_contacts([])) == {}

    async def test_a_partner_link_that_is_no_longer_active_still_counts(
        self, deal_case: DealCase
    ) -> None:
        old = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
        new = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
        deal = make_deal(NOW, code="20261016-A001", partner_id=old.id)
        await deal_case.add(deal)
        await deal_case.replace_partner(deal.id, new.id, later(5))

        counts = await deal_case.deals.count_by_contacts([old.id, new.id])

        assert dict(counts) == {old.id: 1, new.id: 1}

    async def test_one_deal_using_the_contact_twice_counts_once(self, deal_case: DealCase) -> None:
        contact = await deal_case.new_contact()
        await deal_case.ensure_owner()
        await deal_case.deals.add(
            make_deal(code="20261016-A001", customer_id=contact.id, partner_id=contact.id)
        )

        assert dict(await deal_case.deals.count_by_contacts([contact.id])) == {contact.id: 1}

    async def test_deleted_deals_are_forgotten(self, deal_case: DealCase) -> None:
        customer = await deal_case.new_contact()
        deal = make_deal(code="20261016-A001", customer_id=customer.id)
        await deal_case.add(deal)
        await deal_case.deals.delete(deal.id)

        assert dict(await deal_case.deals.count_by_contacts([customer.id])) == {customer.id: 0}
