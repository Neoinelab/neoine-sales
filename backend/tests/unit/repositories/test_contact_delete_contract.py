"""ContactRepository.delete와 DealRepository.count_by_contacts 계약(AC-22).

참조하는 Deal이 있으면 ContactInUseError, 없으면 물리 삭제. Fake(`restrict_delete_by`로 FK
RESTRICT 모사)와 SQL 구현(실제 PostgreSQL FK `fk_deals_customer_id_contacts`,
`fk_deals_partner_id_contacts`)에 같은 테스트를 적용한다. 한 Deal이 같은 연락처를 고객과 파트너로
둘 다 참조하면 1건이다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidStateError
from app.domain.contact.errors import ContactInUseError, ContactNotFoundError
from app.domain.contact.values import ContactId
from tests.factories import make_deal
from tests.factories_contact import make_customer, make_partner
from tests.support.ids import new_id
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from tests.unit.repositories.contact_case import ContactCase


async def test_delete_of_a_contact_without_deals_removes_the_row(contacts: ContactCase) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)

    await contacts.contacts.delete(contact.id)

    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.get(contact.id)


async def test_delete_removes_only_the_requested_contact(contacts: ContactCase) -> None:
    kept, removed = make_customer(company="kept"), make_partner(company="removed")
    await contacts.add_all(kept, removed)

    await contacts.contacts.delete(removed.id)

    assert (await contacts.contacts.get(kept.id)).id == kept.id


async def test_delete_of_a_missing_contact_raises_not_found(contacts: ContactCase) -> None:
    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.delete(ContactId(new_id()))


async def test_deleting_twice_raises_not_found_the_second_time(contacts: ContactCase) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)
    await contacts.contacts.delete(contact.id)

    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.delete(contact.id)


async def test_update_of_a_deleted_contact_raises_not_found(contacts: ContactCase) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)
    await contacts.contacts.delete(contact.id)

    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.update(contact)


async def test_a_deleted_contact_id_can_be_added_again(contacts: ContactCase) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)
    await contacts.contacts.delete(contact.id)

    await contacts.contacts.add(contact)

    assert (await contacts.contacts.get(contact.id)).id == contact.id


async def test_delete_of_a_contact_used_as_the_customer_raises_in_use_and_keeps_the_row(
    contacts: ContactCase,
) -> None:
    customer = make_customer()
    await contacts.contacts.add(customer)
    await contacts.add_deal(customer)

    with pytest.raises(ContactInUseError) as error:
        await contacts.contacts.delete(customer.id)

    assert isinstance(error.value, InvalidStateError)
    assert (await contacts.contacts.get(customer.id)).id == customer.id


async def test_delete_of_a_contact_used_as_the_partner_raises_in_use(
    contacts: ContactCase,
) -> None:
    customer, partner = make_customer(), make_partner()
    await contacts.add_all(customer, partner)
    await contacts.add_deal(customer, partner)

    with pytest.raises(ContactInUseError):
        await contacts.contacts.delete(partner.id)

    assert (await contacts.contacts.get(partner.id)).id == partner.id


async def test_repository_stays_usable_after_an_in_use_conflict(contacts: ContactCase) -> None:
    busy, free = make_customer(company="busy"), make_customer(company="free")
    await contacts.add_all(busy, free)
    await contacts.add_deal(busy)
    with pytest.raises(ContactInUseError):
        await contacts.contacts.delete(busy.id)

    await contacts.contacts.delete(free.id)

    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.get(free.id)


async def test_delete_succeeds_once_the_referencing_deal_is_deleted(contacts: ContactCase) -> None:
    customer = make_customer()
    await contacts.contacts.add(customer)
    deal = await contacts.add_deal(customer)
    await contacts.deals.delete(deal.id)

    await contacts.contacts.delete(customer.id)

    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.get(customer.id)


# --- DealRepository.count_by_contacts ---


async def test_count_by_contacts_counts_customer_and_partner_references(
    contacts: ContactCase,
) -> None:
    customer, partner, idle = make_customer(), make_partner(), make_customer(company="idle")
    await contacts.add_all(customer, partner, idle)
    await contacts.add_deal(customer, partner, code="20261016-D001")
    await contacts.add_deal(customer, code="20261016-D002")

    counts = await contacts.deals.count_by_contacts([customer.id, partner.id, idle.id])

    assert counts == {customer.id: 2, partner.id: 1, idle.id: 0}


async def test_count_by_contacts_counts_a_deal_using_one_contact_twice_once(
    contacts: ContactCase,
) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)
    deal = make_deal(code="20261016-BOTH", customer_id=contact.id, partner_id=contact.id)

    await ensure_users(contacts.users, deal.details.owner_user_id)
    await contacts.deals.add(deal)

    counts = await contacts.deals.count_by_contacts([contact.id])

    assert counts == {contact.id: 1}


async def test_count_by_contacts_returns_zero_for_unknown_ids_and_an_empty_map_for_none(
    contacts: ContactCase,
) -> None:
    unknown = ContactId(new_id())

    assert await contacts.deals.count_by_contacts([unknown]) == {unknown: 0}
    assert await contacts.deals.count_by_contacts([]) == {}


async def test_count_by_contacts_forgets_deleted_deals(contacts: ContactCase) -> None:
    customer = make_customer()
    await contacts.contacts.add(customer)
    deal = await contacts.add_deal(customer)
    await contacts.deals.delete(deal.id)

    assert await contacts.deals.count_by_contacts([customer.id]) == {customer.id: 0}
