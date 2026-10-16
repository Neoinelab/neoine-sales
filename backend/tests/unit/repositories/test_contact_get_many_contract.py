"""ContactRepository.get_many 계약(R2 리뷰 이월 3, N+1 해소): Fake와 SQL(PostgreSQL)에 같은 기대값.

`get_many(ids)`는 id -> 연락처 매핑을 한 번에 돌려준다. 없는 id는 오류 없이 결과에서 빠지고,
빈 입력은 빈 결과이며, 같은 id가 여러 번 와도 한 번만 담긴다. 각 연락처는 `get`과 같다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from app.domain.contact.values import ContactId, ContactKind
from tests.factories import later
from tests.factories_contact import make_customer, make_partner

if TYPE_CHECKING:
    from tests.unit.repositories.contact_case import ContactCase


async def test_it_returns_every_requested_contact_keyed_by_id(contacts: ContactCase) -> None:
    customer = make_customer(later(1), company="한빛은행", name="정민수")
    partner = make_partner(later(2), company="코어테크", name="민지훈")
    other = make_customer(later(3), company="대한상사", name="오세훈")
    await contacts.add_all(customer, partner, other)

    found = await contacts.contacts.get_many([customer.id, partner.id])

    assert dict(found) == {customer.id: customer, partner.id: partner}


async def test_each_contact_equals_what_get_returns(contacts: ContactCase) -> None:
    customer = make_customer(later(1))
    await contacts.add_all(customer)

    found = await contacts.contacts.get_many([customer.id])

    assert found[customer.id] == await contacts.contacts.get(customer.id)
    assert found[customer.id].kind is ContactKind.CUSTOMER


async def test_unknown_ids_are_left_out_without_an_error(contacts: ContactCase) -> None:
    customer = make_customer(later(1))
    await contacts.add_all(customer)
    unknown = ContactId(uuid4())

    found = await contacts.contacts.get_many([customer.id, unknown])

    assert set(found) == {customer.id}


async def test_empty_input_gives_an_empty_result(contacts: ContactCase) -> None:
    assert dict(await contacts.contacts.get_many([])) == {}


async def test_a_repeated_id_is_returned_once(contacts: ContactCase) -> None:
    customer = make_customer(later(1))
    await contacts.add_all(customer)

    found = await contacts.contacts.get_many([customer.id, customer.id])

    assert dict(found) == {customer.id: customer}


async def test_the_returned_contacts_are_copies(contacts: ContactCase) -> None:
    customer = make_customer(later(1))
    await contacts.add_all(customer)

    first = (await contacts.contacts.get_many([customer.id]))[customer.id]
    first.details = make_customer(company="바꿈", name="바꿈").details

    again = (await contacts.contacts.get_many([customer.id]))[customer.id]
    assert again.details.company != "바꿈"
