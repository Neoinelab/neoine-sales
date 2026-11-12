"""DealRepository 사용 수 집계 계약(Status, 연락처): Fake와 SQL 구현에 같은 테스트를 적용한다.

Status 사용 수는 `deals.status_key` 기준이다(0인 항목은 무시하고 비교한다). Forecast·BANT Label
사용 수와 삭제 FK 매핑은 다른 계약 파일이 맡는다.
연락처 사용 수는 고객 + 파트너 링크(비활성 포함)를 Deal당 1건으로 센다.
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
        """Deal이 없으면 Status 사용 수가 비어 있는지 확인한다."""
        # when: Status별 사용 수를 센다
        counts = await deal_case.deals.count_by_status()

        # then: 0이 아닌 사용 수가 없다
        assert _nonzero(counts) == {}

    async def test_deals_are_grouped_by_status_key(self, deal_case: DealCase) -> None:
        """Deal이 status_key별로 집계되는지 확인한다."""
        # given: Status가 섞인 Deal 네 개를 저장한다
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

        # when: Status별 사용 수를 센다
        counts = await deal_case.deals.count_by_status()

        # then: Status마다 해당 Deal 수다
        assert _nonzero(counts) == {"prospecting": 2, "introduction": 1, "contract_completed": 1}

    async def test_counts_follow_status_changes_and_deletions(self, deal_case: DealCase) -> None:
        """Status 변경과 삭제가 사용 수에 반영되는지 확인한다."""
        # given: Status가 다른 Deal 두 개를 저장한다
        moved = make_deal(later(1), code="20261016-A001")
        removed = make_deal(later(2), code="20261016-A002", status_key="introduction")
        await deal_case.add(moved)
        await deal_case.add(removed)

        # when: 하나는 Status를 바꾸고 다른 하나는 삭제한다
        await deal_case.revise(moved.id, sync=make_deal(status_key="price_negotiation").sync)
        await deal_case.deals.delete(removed.id)

        # when: Status별 사용 수를 센다
        counts = await deal_case.deals.count_by_status()

        # then: 삭제하지 않은 Deal 하나가 새 Status로 집계된다
        assert _nonzero(counts) == {"price_negotiation": 1}


class TestCountByContacts:
    async def test_counts_customers_and_partners_and_zero_for_unused_contacts(
        self, deal_case: DealCase
    ) -> None:
        """고객·파트너 연락처 사용 수와 미사용 연락처의 0을 세는지 확인한다."""
        # given: 고객, 파트너, 미사용 연락처와 이를 쓰는 Deal 두 개가 있다
        customer = await deal_case.new_contact()
        partner = await deal_case.new_contact(ContactKind.PARTNER)
        idle = await deal_case.new_contact(company="안쓰는곳", name="무명")
        await deal_case.add(
            make_deal(code="20261016-A001", customer_id=customer.id, partner_id=partner.id)
        )
        await deal_case.add(make_deal(code="20261016-A002", customer_id=customer.id))

        # when: 세 연락처의 사용 수를 센다
        counts = await deal_case.deals.count_by_contacts([customer.id, partner.id, idle.id])

        # then: 고객 2, 파트너 1, 미사용 0이다
        assert dict(counts) == {customer.id: 2, partner.id: 1, idle.id: 0}

    async def test_an_unknown_contact_is_zero_and_empty_input_is_empty(
        self, deal_case: DealCase
    ) -> None:
        """모르는 연락처는 0이고 빈 입력은 빈 결과인지 확인한다."""
        # given: 어느 Deal에도 쓰이지 않는 연락처 id가 있다
        unknown = new_contact_id()

        # when: 모르는 연락처의 사용 수를 센다
        counts_unknown = await deal_case.deals.count_by_contacts([unknown])

        # then: 0이다
        assert dict(counts_unknown) == {unknown: 0}

        # when: 빈 입력으로 사용 수를 센다
        counts_empty = await deal_case.deals.count_by_contacts([])

        # then: 빈 결과다
        assert dict(counts_empty) == {}

    async def test_a_partner_link_that_is_no_longer_active_still_counts(
        self, deal_case: DealCase
    ) -> None:
        """더는 활성이 아닌 파트너 링크도 사용 수에 포함되는지 확인한다."""
        # given: 파트너가 새 파트너로 교체된 Deal이 있다
        old = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
        new = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
        deal = make_deal(NOW, code="20261016-A001", partner_id=old.id)
        await deal_case.add(deal)
        await deal_case.replace_partner(deal.id, new.id, later(5))

        # when: 이전·새 파트너의 사용 수를 센다
        counts = await deal_case.deals.count_by_contacts([old.id, new.id])

        # then: 둘 다 1이다
        assert dict(counts) == {old.id: 1, new.id: 1}

    async def test_one_deal_using_the_contact_twice_counts_once(self, deal_case: DealCase) -> None:
        """한 Deal이 같은 연락처를 두 번 써도 1건인지 확인한다."""
        # given: 고객과 파트너에 같은 연락처를 쓰는 Deal이 있다
        contact = await deal_case.new_contact()
        await deal_case.ensure_owner()
        await deal_case.deals.add(
            make_deal(code="20261016-A001", customer_id=contact.id, partner_id=contact.id)
        )

        # when: 연락처 사용 수를 센다
        counts = await deal_case.deals.count_by_contacts([contact.id])

        # then: 1이다
        assert dict(counts) == {contact.id: 1}

    async def test_deleted_deals_are_forgotten(self, deal_case: DealCase) -> None:
        """삭제된 Deal은 사용 수에서 빠지는지 확인한다."""
        # given: 연락처를 쓰는 Deal을 저장했다가 삭제한다
        customer = await deal_case.new_contact()
        deal = make_deal(code="20261016-A001", customer_id=customer.id)
        await deal_case.add(deal)
        await deal_case.deals.delete(deal.id)

        # when: 연락처 사용 수를 센다
        counts = await deal_case.deals.count_by_contacts([customer.id])

        # then: 0이다
        assert dict(counts) == {customer.id: 0}
