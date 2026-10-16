"""DealRepository.references_of_contact 계약(R2, AC-10·Q11): 연락처를 참조하는 Deal과 역할.

고객 참조는 CUSTOMER, 파트너 링크는 **비활성 링크를 포함해** PARTNER다. 연락처 갱신 이력을 어느
Deal에 남길지 이 목록이 정한다. Fake와 SQL(PostgreSQL)에 같은 기대값을 적용한다.
"""

from typing import TYPE_CHECKING

from app.domain.contact.values import ContactKind
from tests.factories import NOW, later, make_deal
from tests.support.user_ids import OWNER_ID  # noqa: F401 - 소유자 행은 case가 만든다

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


async def _refs(case: DealCase, contact_id: object) -> list[tuple[str, str]]:
    found = await case.deals.references_of_contact(contact_id)
    return sorted((ref.deal_code.value, str(ref.role)) for ref in found)


async def test_an_unused_contact_has_no_references(deal_case: DealCase) -> None:
    contact = await deal_case.new_contact()

    assert list(await deal_case.deals.references_of_contact(contact.id)) == []


async def test_a_customer_reference_is_reported_per_deal(deal_case: DealCase) -> None:
    customer = await deal_case.new_contact()
    await deal_case.add(make_deal(code="20261016-A001", customer_id=customer.id))
    await deal_case.add(make_deal(code="20261016-A002", customer_id=customer.id))
    await deal_case.add(make_deal(code="20261016-A003"))  # 다른 고객

    assert await _refs(deal_case, customer.id) == [
        ("20261016-A001", "customer"),
        ("20261016-A002", "customer"),
    ]


async def test_an_active_partner_link_is_reported_as_a_partner_reference(
    deal_case: DealCase,
) -> None:
    partner = await deal_case.new_contact(ContactKind.PARTNER)
    await deal_case.add(make_deal(code="20261016-A001", partner_id=partner.id))

    assert await _refs(deal_case, partner.id) == [("20261016-A001", "partner")]


async def test_a_partner_link_that_is_no_longer_active_is_still_reported(
    deal_case: DealCase,
) -> None:
    old = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
    new = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
    deal = make_deal(NOW, code="20261016-A001", partner_id=old.id)
    await deal_case.add(deal)
    await deal_case.replace_partner(deal.id, new.id, later(5))

    assert await _refs(deal_case, old.id) == [("20261016-A001", "partner")]
    assert await _refs(deal_case, new.id) == [("20261016-A001", "partner")]


async def test_a_contact_used_as_customer_and_partner_of_the_same_deal_has_both_roles(
    deal_case: DealCase,
) -> None:
    contact = await deal_case.new_contact()
    await deal_case.ensure_owner()
    await deal_case.deals.add(
        make_deal(code="20261016-A001", customer_id=contact.id, partner_id=contact.id)
    )

    assert await _refs(deal_case, contact.id) == [
        ("20261016-A001", "customer"),
        ("20261016-A001", "partner"),
    ]


async def test_a_deleted_deal_no_longer_references_the_contact(deal_case: DealCase) -> None:
    customer = await deal_case.new_contact()
    deal = make_deal(code="20261016-A001", customer_id=customer.id)
    await deal_case.add(deal)

    await deal_case.deals.delete(deal.id)

    assert list(await deal_case.deals.references_of_contact(customer.id)) == []
