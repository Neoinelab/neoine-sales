"""Contact 엔티티: 생성·수정·동등성, 구분(kind)은 생성 뒤 바뀌지 않는다(AC-21).

고객·파트너를 한 엔티티로 합쳤으므로 구 test_entity_lifecycle.py의 Customer/Partner 항목은 여기서
`kind` 두 값으로 다시 확인한다.
"""

from datetime import UTC, datetime

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.contact.entities import Contact
from app.domain.contact.values import ContactId, ContactKind
from tests.factories import NOW, later
from tests.factories_contact import make_contact, make_contact_details
from tests.support.ids import new_id

KINDS = list(ContactKind)


@pytest.mark.parametrize("kind", KINDS)
def test_create_assigns_id_kind_and_timestamps(kind: ContactKind) -> None:
    contact = make_contact(kind, NOW)

    assert contact.id is not None
    assert contact.kind is kind
    assert contact.created_at == NOW
    assert contact.updated_at == NOW


def test_create_uses_the_given_id() -> None:
    entity_id = ContactId(new_id())

    contact = make_contact(entity_id=entity_id)

    assert contact.id == entity_id


def test_create_rejects_naive_datetime() -> None:
    with pytest.raises(InvalidValueError):
        Contact.create(
            ContactKind.CUSTOMER,
            make_contact_details(),
            datetime(2026, 1, 1),
            entity_id=ContactId(new_id()),
        )


@pytest.mark.parametrize("kind", KINDS)
def test_update_replaces_details_and_bumps_updated_at(kind: ContactKind) -> None:
    contact = make_contact(kind, NOW)
    new_details = make_contact_details(kind, company="다른회사", title=None)

    contact.update(new_details, later(60))

    assert contact.details == new_details
    assert contact.updated_at == later(60)
    assert contact.created_at == NOW


@pytest.mark.parametrize("kind", KINDS)
def test_update_keeps_the_kind(kind: ContactKind) -> None:
    contact = make_contact(kind)

    contact.update(make_contact_details(kind, company="다른회사"), later(5))

    assert contact.kind is kind


def test_update_has_no_way_to_change_the_kind() -> None:
    contact = make_contact(ContactKind.CUSTOMER)

    with pytest.raises(TypeError):
        contact.update(  # type: ignore[call-arg, unused-ignore]
            make_contact_details(), later(5), kind=ContactKind.PARTNER
        )

    assert contact.kind is ContactKind.CUSTOMER


def test_update_rejects_naive_datetime() -> None:
    contact = make_contact()

    with pytest.raises(InvalidValueError):
        contact.update(make_contact_details(company="다른회사"), datetime(2026, 1, 2))


def test_contacts_are_equal_when_ids_match_regardless_of_details() -> None:
    original = make_contact()
    same_id = make_contact(entity_id=original.id, company="다른회사")

    assert original == same_id
    assert hash(original) == hash(same_id)
    assert len({original, same_id}) == 1


def test_contacts_with_different_ids_are_not_equal() -> None:
    assert make_contact() != make_contact()


def test_timestamps_passed_to_constructor_must_be_timezone_aware() -> None:
    with pytest.raises(InvalidValueError):
        Contact(
            id=new_id(),  # type: ignore[arg-type, unused-ignore]
            kind=ContactKind.CUSTOMER,
            details=make_contact_details(),
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
