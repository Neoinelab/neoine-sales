"""ContactRepository.get_many 계약: Fake와 SQL(PostgreSQL)에 같은 기대값.

`get_many(ids)`는 id -> 연락처 매핑을 한 번에 돌려준다. 없는 id는 오류 없이 결과에서 빠지고,
빈 입력은 빈 결과이며, 같은 id가 여러 번 와도 한 번만 담긴다. 각 연락처는 `get`과 같다.
"""

from typing import TYPE_CHECKING

from app.domain.contact.values import ContactId, ContactKind
from tests.factories import later
from tests.factories_contact import make_customer, make_partner
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.contact_case import ContactCase


async def test_it_returns_every_requested_contact_keyed_by_id(contacts: ContactCase) -> None:
    """요청한 연락처를 id별로 모두 돌려준다."""
    # given: 연락처 세 개
    customer = make_customer(later(1), company="한빛은행", name="정민수")
    partner = make_partner(later(2), company="코어테크", name="민지훈")
    other = make_customer(later(3), company="대한상사", name="오세훈")
    await contacts.add_all(customer, partner, other)

    # when: 그중 두 개를 일괄 조회한다
    found = await contacts.contacts.get_many([customer.id, partner.id])

    # then: 요청한 두 개만 id를 키로 담긴다
    assert dict(found) == {customer.id: customer, partner.id: partner}


async def test_each_contact_equals_what_get_returns(contacts: ContactCase) -> None:
    """일괄 조회한 연락처는 get의 결과와 같다."""
    # given: 고객 연락처
    customer = make_customer(later(1))
    await contacts.add_all(customer)

    # when: 일괄 조회한다
    found = await contacts.contacts.get_many([customer.id])

    # then: get 결과와 같고 종류가 고객이다
    assert found[customer.id] == await contacts.contacts.get(customer.id)
    assert found[customer.id].kind is ContactKind.CUSTOMER


async def test_unknown_ids_are_left_out_without_an_error(contacts: ContactCase) -> None:
    """없는 id는 오류 없이 결과에서 빠진다."""
    # given: 고객 연락처와 없는 id
    customer = make_customer(later(1))
    await contacts.add_all(customer)
    unknown = ContactId(new_id())

    # when: 둘을 일괄 조회한다
    found = await contacts.contacts.get_many([customer.id, unknown])

    # then: 있는 연락처만 담긴다
    assert set(found) == {customer.id}


async def test_empty_input_gives_an_empty_result(contacts: ContactCase) -> None:
    """빈 입력은 빈 결과다."""
    # when: 빈 목록으로 일괄 조회한다
    result = dict(await contacts.contacts.get_many([]))
    # then: 빈 결과다
    assert result == {}


async def test_a_repeated_id_is_returned_once(contacts: ContactCase) -> None:
    """같은 id가 반복돼도 한 번만 담긴다."""
    # given: 고객 연락처
    customer = make_customer(later(1))
    await contacts.add_all(customer)

    # when: 같은 id를 두 번 넣어 일괄 조회한다
    found = await contacts.contacts.get_many([customer.id, customer.id])

    # then: 한 번만 담긴다
    assert dict(found) == {customer.id: customer}


async def test_the_returned_contacts_are_copies(contacts: ContactCase) -> None:
    """돌려준 연락처를 바꿔도 저장소에는 영향이 없다."""
    # given: 고객 연락처
    customer = make_customer(later(1))
    await contacts.add_all(customer)

    # when: 조회한 결과의 내용을 바꾼다
    first = (await contacts.contacts.get_many([customer.id]))[customer.id]
    first.details = make_customer(company="바꿈", name="바꿈").details

    # when: 다시 조회한다
    again = (await contacts.contacts.get_many([customer.id]))[customer.id]
    # then: 저장된 회사명은 그대로다
    assert again.details.company != "바꿈"
