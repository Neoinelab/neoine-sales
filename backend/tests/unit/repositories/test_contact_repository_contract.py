"""ContactRepository CRUD 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

구 Customer/Partner Repository 계약(add/get/update/delete, 복사본 저장)을 contacts 하나로 옮겼다.
조회(search·count·companies·of_company·same_identity)는 test_contact_search_contract.py,
삭제와 Deal 참조는 test_contact_delete_contract.py다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import AlreadyExistsError
from app.domain.contact.errors import ContactNotFoundError
from app.domain.contact.values import ContactId, ContactKind
from tests.factories import later
from tests.factories_contact import make_contact, make_contact_details, make_customer, make_partner
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.contact_case import ContactCase

KINDS = list(ContactKind)


def _missing_id() -> ContactId:
    return ContactId(new_id())


@pytest.mark.parametrize("kind", KINDS)
async def test_add_then_get_returns_an_equal_but_separate_contact(
    contacts: ContactCase, kind: ContactKind
) -> None:
    contact = make_contact(kind, later(1))
    await contacts.contacts.add(contact)

    loaded = await contacts.contacts.get(contact.id)

    assert loaded == contact
    assert loaded is not contact
    assert loaded.kind is kind
    assert loaded.details == contact.details
    assert (loaded.created_at, loaded.updated_at) == (later(1), later(1))


async def test_every_optional_field_survives_a_round_trip(contacts: ContactCase) -> None:
    full = make_customer(company="Full", name="One", title="수석 팀장", phone="+82-10-1234-5678")
    bare = make_customer(company="Bare", name="Two", title=None, email=None, phone=None)
    await contacts.add_all(full, bare)

    loaded_full = await contacts.contacts.get(full.id)
    loaded_bare = await contacts.contacts.get(bare.id)

    assert loaded_full.details == full.details
    assert loaded_full.details.title == "수석 팀장"
    assert loaded_full.details.phone is not None
    assert loaded_full.details.phone.value == "+82-10-1234-5678"
    assert (loaded_bare.details.title, loaded_bare.details.email, loaded_bare.details.phone) == (
        None,
        None,
        None,
    )


async def test_get_missing_contact_raises_not_found(contacts: ContactCase) -> None:
    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.get(_missing_id())


async def test_get_with_a_row_lock_returns_the_same_contact(contacts: ContactCase) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)

    locked = await contacts.contacts.get(contact.id, for_update=True)

    assert locked == contact
    assert locked.details == contact.details


async def test_add_with_an_existing_id_raises_already_exists(contacts: ContactCase) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)

    with pytest.raises(AlreadyExistsError):
        await contacts.contacts.add(contact)


async def test_the_repository_stays_usable_after_a_conflict(contacts: ContactCase) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)
    with pytest.raises(AlreadyExistsError):
        await contacts.contacts.add(contact)

    other = make_customer(company="다른회사")
    await contacts.contacts.add(other)

    assert (await contacts.contacts.get(other.id)).id == other.id


async def test_two_contacts_of_the_same_person_can_be_stored(contacts: ContactCase) -> None:
    """같은 사람 판정은 유스케이스의 몫이라, 저장소는 같은 회사·담당자도 거절하지 않는다."""
    first = make_customer(email="kim1@neoine.example")
    second = make_customer(email="kim2@neoine.example")

    await contacts.add_all(first, second)

    assert (await contacts.contacts.get(second.id)).id == second.id


async def test_update_persists_changes_and_keeps_kind_and_created_at(
    contacts: ContactCase,
) -> None:
    original = make_partner(later(1))
    await contacts.contacts.add(original)
    loaded = await contacts.contacts.get(original.id)
    loaded.update(
        make_contact_details(ContactKind.PARTNER, company="변경회사", title=None), later(100)
    )

    await contacts.contacts.update(loaded)
    reloaded = await contacts.contacts.get(original.id)

    assert reloaded.details == loaded.details
    assert reloaded.details.company == "변경회사"
    assert reloaded.details.title is None
    assert reloaded.updated_at == later(100)
    assert reloaded.created_at == later(1)
    assert reloaded.kind is ContactKind.PARTNER


async def test_update_of_a_missing_contact_raises_not_found(contacts: ContactCase) -> None:
    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.update(make_customer())


async def test_changes_to_a_loaded_contact_are_not_saved_without_update(
    contacts: ContactCase,
) -> None:
    original = make_customer()
    await contacts.contacts.add(original)
    loaded = await contacts.contacts.get(original.id)

    loaded.update(make_contact_details(company="저장안함"), later(100))
    reloaded = await contacts.contacts.get(original.id)

    assert reloaded.details == original.details


async def test_changes_to_an_added_contact_are_not_saved_without_update(
    contacts: ContactCase,
) -> None:
    contact = make_customer()
    original_details = contact.details
    await contacts.contacts.add(contact)

    contact.update(make_contact_details(company="저장안함"), later(100))
    reloaded = await contacts.contacts.get(contact.id)

    assert reloaded.details == original_details


async def test_integer_ids_are_kept_as_given(contacts: ContactCase) -> None:
    given = 7_654_321_098
    contact = make_customer(entity_id=ContactId(given))

    await contacts.contacts.add(contact)

    assert (await contacts.contacts.get(ContactId(given))).id == given
