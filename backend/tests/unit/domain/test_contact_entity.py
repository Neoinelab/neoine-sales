"""Contact 엔티티: 생성·수정·동등성, 구분(kind)은 생성 뒤 바뀌지 않는다.

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
    """연락처를 만들면 id, 구분, 생성·수정 시각이 정해진다."""
    # when: 해당 구분의 연락처를 만든다
    contact = make_contact(kind, NOW)

    # then: id가 있고 구분이 같으며 생성·수정 시각이 현재다
    assert contact.id is not None
    assert contact.kind is kind
    assert contact.created_at == NOW
    assert contact.updated_at == NOW


def test_create_uses_the_given_id() -> None:
    """연락처를 만들 때 준 id를 그대로 쓴다."""
    # given: 연락처 id
    entity_id = ContactId(new_id())

    # when: 그 id로 연락처를 만든다
    contact = make_contact(entity_id=entity_id)

    # then: 연락처 id가 준 값이다
    assert contact.id == entity_id


def test_create_rejects_naive_datetime() -> None:
    """시간대 없는 시각으로는 연락처를 만들 수 없다."""
    # when·then: 시간대 없는 시각으로 만들면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        Contact.create(
            ContactKind.CUSTOMER,
            make_contact_details(),
            datetime(2026, 1, 1),
            entity_id=ContactId(new_id()),
        )


@pytest.mark.parametrize("kind", KINDS)
def test_update_replaces_details_and_bumps_updated_at(kind: ContactKind) -> None:
    """수정하면 상세가 바뀌고 수정 시각만 갱신된다."""
    # given: 연락처와 회사·직급을 바꾼 새 상세
    contact = make_contact(kind, NOW)
    new_details = make_contact_details(kind, company="다른회사", title=None)

    # when: 60분 뒤 새 상세로 수정한다
    contact.update(new_details, later(60))

    # then: 상세와 수정 시각이 바뀌고 생성 시각은 그대로다
    assert contact.details == new_details
    assert contact.updated_at == later(60)
    assert contact.created_at == NOW


@pytest.mark.parametrize("kind", KINDS)
def test_update_keeps_the_kind(kind: ContactKind) -> None:
    """수정해도 구분은 그대로다."""
    # given: 해당 구분의 연락처
    contact = make_contact(kind)

    # when: 상세를 수정한다
    contact.update(make_contact_details(kind, company="다른회사"), later(5))

    # then: 구분이 그대로다
    assert contact.kind is kind


def test_update_has_no_way_to_change_the_kind() -> None:
    """수정 메서드로는 구분을 바꿀 수 없다."""
    # given: 고객 구분 연락처
    contact = make_contact(ContactKind.CUSTOMER)

    # when·then: 수정에 kind 인자를 주면 TypeError다
    with pytest.raises(TypeError):
        contact.update(  # type: ignore[call-arg, unused-ignore]
            make_contact_details(), later(5), kind=ContactKind.PARTNER
        )

    # then: 구분은 그대로 고객이다
    assert contact.kind is ContactKind.CUSTOMER


def test_update_rejects_naive_datetime() -> None:
    """시간대 없는 시각으로는 연락처를 수정할 수 없다."""
    # given: 연락처
    contact = make_contact()

    # when·then: 시간대 없는 시각으로 수정하면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        contact.update(make_contact_details(company="다른회사"), datetime(2026, 1, 2))


def test_contacts_are_equal_when_ids_match_regardless_of_details() -> None:
    """id가 같으면 상세가 달라도 같은 연락처로 비교된다."""
    # given: 같은 id에 회사만 다른 연락처 둘
    original = make_contact()
    same_id = make_contact(entity_id=original.id, company="다른회사")

    # when: 둘을 비교하고 해시와 집합 크기를 구한다
    equal = original == same_id
    hashes = (hash(original), hash(same_id))
    unique_count = len({original, same_id})
    # then: 둘은 같고 해시도 같으며 집합에서 하나로 합쳐진다
    assert equal
    assert hashes[0] == hashes[1]
    assert unique_count == 1


def test_contacts_with_different_ids_are_not_equal() -> None:
    """id가 다르면 다른 연락처다."""
    # when: 서로 다른 id의 연락처 둘을 만든다
    first = make_contact()
    second = make_contact()
    # then: 둘은 같지 않다
    assert first != second


def test_timestamps_passed_to_constructor_must_be_timezone_aware() -> None:
    """생성자에 주는 시각은 시간대가 있어야 한다."""
    # when·then: 시간대 없는 생성 시각을 주면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        Contact(
            id=new_id(),  # type: ignore[arg-type, unused-ignore]
            kind=ContactKind.CUSTOMER,
            details=make_contact_details(),
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
