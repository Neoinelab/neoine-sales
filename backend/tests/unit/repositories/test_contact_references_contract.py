"""DealRepository.references_of_contact 계약: 연락처를 참조하는 Deal과 역할.

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
    """어느 Deal에도 쓰이지 않는 연락처는 참조가 없다."""
    # given: 쓰이지 않는 연락처
    contact = await deal_case.new_contact()

    # when: 연락처의 참조를 조회한다
    refs = list(await deal_case.deals.references_of_contact(contact.id))

    # then: 비어 있다
    assert refs == []


async def test_a_customer_reference_is_reported_per_deal(deal_case: DealCase) -> None:
    """고객 참조는 Deal마다 CUSTOMER 역할로 나온다."""
    # given: 고객 연락처를 쓰는 Deal 둘과 다른 고객의 Deal
    customer = await deal_case.new_contact()
    await deal_case.add(make_deal(code="20261016-A001", customer_id=customer.id))
    await deal_case.add(make_deal(code="20261016-A002", customer_id=customer.id))
    await deal_case.add(make_deal(code="20261016-A003"))  # 다른 고객

    # when: 고객 연락처의 참조를 조회한다
    refs = await _refs(deal_case, customer.id)

    # then: 그 연락처를 쓰는 두 Deal이 customer 역할로 나온다
    assert refs == [
        ("20261016-A001", "customer"),
        ("20261016-A002", "customer"),
    ]


async def test_an_active_partner_link_is_reported_as_a_partner_reference(
    deal_case: DealCase,
) -> None:
    """활성 파트너 링크는 PARTNER 참조로 나온다."""
    # given: 파트너 연락처가 연결된 Deal
    partner = await deal_case.new_contact(ContactKind.PARTNER)
    await deal_case.add(make_deal(code="20261016-A001", partner_id=partner.id))

    # when: 파트너 연락처의 참조를 조회한다
    refs = await _refs(deal_case, partner.id)

    # then: partner 역할로 나온다
    assert refs == [("20261016-A001", "partner")]


async def test_a_partner_link_that_is_no_longer_active_is_still_reported(
    deal_case: DealCase,
) -> None:
    """비활성이 된 파트너 링크도 PARTNER 참조로 나온다."""
    # given: 파트너가 새 파트너로 교체된 Deal
    old = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
    new = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
    deal = make_deal(NOW, code="20261016-A001", partner_id=old.id)
    await deal_case.add(deal)
    await deal_case.replace_partner(deal.id, new.id, later(5))

    # when: 이전·새 파트너의 참조를 조회한다
    old_refs = await _refs(deal_case, old.id)
    new_refs = await _refs(deal_case, new.id)

    # then: 둘 다 partner 역할로 같은 Deal을 가리킨다
    assert old_refs == [("20261016-A001", "partner")]
    assert new_refs == [("20261016-A001", "partner")]


async def test_a_contact_used_as_customer_and_partner_of_the_same_deal_has_both_roles(
    deal_case: DealCase,
) -> None:
    """한 연락처가 같은 Deal의 고객이자 파트너면 두 역할이 모두 나온다."""
    # given: 같은 연락처를 고객과 파트너로 쓰는 Deal
    contact = await deal_case.new_contact()
    await deal_case.ensure_owner()
    await deal_case.deals.add(
        make_deal(code="20261016-A001", customer_id=contact.id, partner_id=contact.id)
    )

    # when: 연락처의 참조를 조회한다
    refs = await _refs(deal_case, contact.id)

    # then: customer와 partner 역할이 모두 나온다
    assert refs == [
        ("20261016-A001", "customer"),
        ("20261016-A001", "partner"),
    ]


async def test_a_deleted_deal_no_longer_references_the_contact(deal_case: DealCase) -> None:
    """삭제된 Deal은 더 이상 연락처를 참조하지 않는다."""
    # given: 고객 연락처를 쓰는 Deal
    customer = await deal_case.new_contact()
    deal = make_deal(code="20261016-A001", customer_id=customer.id)
    await deal_case.add(deal)

    # when: Deal을 삭제한다
    await deal_case.deals.delete(deal.id)

    # then: 연락처의 참조가 없다
    assert list(await deal_case.deals.references_of_contact(customer.id)) == []
