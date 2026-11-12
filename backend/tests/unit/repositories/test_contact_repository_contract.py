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
    """추가한 연락처를 읽으면 같은 값의 별도 객체를 얻는다."""
    # given: 추가한 연락처
    contact = make_contact(kind, later(1))
    await contacts.contacts.add(contact)

    # when: 조회한다 (전제: Fake·SQL 공통)
    loaded = await contacts.contacts.get(contact.id)

    # then: 값은 같고 객체는 다르며 종류·시각이 보존된다
    assert loaded == contact
    assert loaded is not contact
    assert loaded.kind is kind
    assert loaded.details == contact.details
    assert (loaded.created_at, loaded.updated_at) == (later(1), later(1))


async def test_every_optional_field_survives_a_round_trip(contacts: ContactCase) -> None:
    """선택 항목이 있어도 없어도 저장 후 그대로 읽힌다."""
    # given: 선택 항목을 모두 채운 연락처와 모두 비운 연락처
    full = make_customer(company="Full", name="One", title="수석 팀장", phone="+82-10-1234-5678")
    bare = make_customer(company="Bare", name="Two", title=None, email=None, phone=None)
    await contacts.add_all(full, bare)

    # when: 둘을 각각 조회한다 (전제: Fake·SQL 공통)
    loaded_full = await contacts.contacts.get(full.id)
    loaded_bare = await contacts.contacts.get(bare.id)

    # then: 값이 그대로 보존된다
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
    """없는 연락처를 조회하면 없음 오류다."""
    # when·then: 없는 id를 조회하면 ContactNotFoundError가 난다 (전제: Fake·SQL 공통)
    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.get(_missing_id())


async def test_get_with_a_row_lock_returns_the_same_contact(contacts: ContactCase) -> None:
    """행 잠금으로 조회해도 같은 연락처를 얻는다."""
    # given: 추가한 연락처
    contact = make_customer()
    await contacts.contacts.add(contact)

    # when: 행 잠금(for_update)으로 조회한다 (전제: Fake·SQL 공통)
    locked = await contacts.contacts.get(contact.id, for_update=True)

    # then: 같은 연락처다
    assert locked == contact
    assert locked.details == contact.details


async def test_add_with_an_existing_id_raises_already_exists(contacts: ContactCase) -> None:
    """이미 있는 id로 추가하면 중복 오류다."""
    # given: 추가한 연락처
    contact = make_customer()
    await contacts.contacts.add(contact)

    # when·then: 같은 id로 다시 추가하면 AlreadyExistsError가 난다 (전제: Fake·SQL 공통)
    with pytest.raises(AlreadyExistsError):
        await contacts.contacts.add(contact)


async def test_the_repository_stays_usable_after_a_conflict(contacts: ContactCase) -> None:
    """중복 오류 뒤에도 저장소를 계속 쓸 수 있다."""
    # given: 중복 오류를 한 번 겪은 저장소
    contact = make_customer()
    await contacts.contacts.add(contact)
    with pytest.raises(AlreadyExistsError):
        await contacts.contacts.add(contact)

    # when: 다른 연락처를 추가한다 (전제: Fake·SQL 공통)
    other = make_customer(company="다른회사")
    await contacts.contacts.add(other)

    # then: 조회할 수 있다
    assert (await contacts.contacts.get(other.id)).id == other.id


async def test_two_contacts_of_the_same_person_can_be_stored(contacts: ContactCase) -> None:
    """같은 사람 판정은 유스케이스의 몫이라, 저장소는 같은 회사·담당자도 거절하지 않는다."""
    # given: 같은 회사·담당자이고 이메일만 다른 두 연락처
    first = make_customer(email="kim1@neoine.example")
    second = make_customer(email="kim2@neoine.example")

    # when: 둘을 추가한다 (전제: Fake·SQL 공통)
    await contacts.add_all(first, second)

    # then: 둘 다 저장되어 조회된다
    assert (await contacts.contacts.get(second.id)).id == second.id


async def test_update_persists_changes_and_keeps_kind_and_created_at(
    contacts: ContactCase,
) -> None:
    """수정은 변경 내용을 저장하고 종류와 생성 시각은 유지한다."""
    # given: 추가한 파트너 연락처와 변경한 객체
    original = make_partner(later(1))
    await contacts.contacts.add(original)
    loaded = await contacts.contacts.get(original.id)
    loaded.update(
        make_contact_details(ContactKind.PARTNER, company="변경회사", title=None), later(100)
    )

    # when: 수정을 저장하고 다시 읽는다 (전제: Fake·SQL 공통)
    await contacts.contacts.update(loaded)
    reloaded = await contacts.contacts.get(original.id)

    # then: 변경 내용은 반영되고 종류·생성 시각은 그대로다
    assert reloaded.details == loaded.details
    assert reloaded.details.company == "변경회사"
    assert reloaded.details.title is None
    assert reloaded.updated_at == later(100)
    assert reloaded.created_at == later(1)
    assert reloaded.kind is ContactKind.PARTNER


async def test_update_of_a_missing_contact_raises_not_found(contacts: ContactCase) -> None:
    """없는 연락처를 수정하면 없음 오류다."""
    # when·then: 저장되지 않은 연락처를 수정하면 ContactNotFoundError가 난다 (전제: Fake·SQL 공통)
    with pytest.raises(ContactNotFoundError):
        await contacts.contacts.update(make_customer())


async def test_changes_to_a_loaded_contact_are_not_saved_without_update(
    contacts: ContactCase,
) -> None:
    """읽어 온 연락처를 고쳐도 update 없이는 저장되지 않는다."""
    # given: 추가한 연락처를 읽어 온 객체
    original = make_customer()
    await contacts.contacts.add(original)
    loaded = await contacts.contacts.get(original.id)

    # when: 객체만 고치고 저장하지 않은 채 다시 읽는다 (전제: Fake·SQL 공통)
    loaded.update(make_contact_details(company="저장안함"), later(100))
    reloaded = await contacts.contacts.get(original.id)

    # then: 저장된 값은 원래대로다
    assert reloaded.details == original.details


async def test_changes_to_an_added_contact_are_not_saved_without_update(
    contacts: ContactCase,
) -> None:
    """추가한 객체를 고쳐도 update 없이는 저장되지 않는다."""
    # given: 추가한 연락처 객체
    contact = make_customer()
    original_details = contact.details
    await contacts.contacts.add(contact)

    # when: 객체만 고치고 저장하지 않은 채 다시 읽는다 (전제: Fake·SQL 공통)
    contact.update(make_contact_details(company="저장안함"), later(100))
    reloaded = await contacts.contacts.get(contact.id)

    # then: 저장된 값은 추가할 때 그대로다
    assert reloaded.details == original_details


async def test_integer_ids_are_kept_as_given(contacts: ContactCase) -> None:
    """지정한 정수 id가 그대로 저장된다."""
    # given: 큰 정수 id를 가진 연락처
    given = 7_654_321_098
    contact = make_customer(entity_id=ContactId(given))

    # when: 추가한다 (전제: Fake·SQL 공통)
    await contacts.contacts.add(contact)

    # then: 같은 id로 조회된다
    assert (await contacts.contacts.get(ContactId(given))).id == given
