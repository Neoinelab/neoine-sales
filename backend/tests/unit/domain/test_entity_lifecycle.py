"""Customer, Partner, Deal이 공유하는 생성·수정·동등성 규칙."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.customer.entities import Customer
from app.domain.deal.entities import Deal
from app.domain.partner.entities import Partner
from tests.factories import (
    NOW,
    later,
    make_customer,
    make_customer_details,
    make_deal,
    make_deal_details,
    make_partner,
    make_partner_details,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class Kind:
    name: str
    entity_type: Any
    make: Callable[..., Any]
    other_details: Callable[[], Any]


KINDS = [
    Kind(
        "customer", Customer, make_customer, lambda: make_customer_details(company_name="다른회사")
    ),
    Kind("partner", Partner, make_partner, lambda: make_partner_details(company_name="다른파트너")),
    Kind("deal", Deal, make_deal, lambda: make_deal_details(name="다른 딜")),
]


@pytest.fixture(params=KINDS, ids=[k.name for k in KINDS])
def kind(request: pytest.FixtureRequest) -> Kind:
    result: Kind = request.param
    return result


def test_create_assigns_id_and_timestamps(kind: Kind) -> None:
    entity = kind.make(NOW)

    assert entity.id is not None
    assert entity.created_at == NOW
    assert entity.updated_at == NOW


def test_create_generates_a_distinct_id_each_time(kind: Kind) -> None:
    assert kind.make().id != kind.make().id


def test_create_accepts_an_explicit_id(kind: Kind) -> None:
    entity_id = uuid4()
    details = kind.make().details

    entity = kind.entity_type.create(details, NOW, entity_id=entity_id)

    assert entity.id == entity_id


def test_create_rejects_naive_datetime(kind: Kind) -> None:
    with pytest.raises(InvalidValueError):
        kind.entity_type.create(kind.make().details, datetime(2026, 1, 1))


def test_update_replaces_details_and_bumps_updated_at(kind: Kind) -> None:
    entity = kind.make(NOW)
    new_details = kind.other_details()

    entity.update(new_details, later(60))

    assert entity.details == new_details
    assert entity.updated_at == later(60)
    assert entity.created_at == NOW


def test_update_rejects_naive_datetime(kind: Kind) -> None:
    entity = kind.make()

    with pytest.raises(InvalidValueError):
        entity.update(kind.other_details(), datetime(2026, 1, 2))


def test_entities_are_equal_when_ids_match_regardless_of_details(kind: Kind) -> None:
    original = kind.make()
    same_id = kind.entity_type.create(kind.other_details(), NOW, entity_id=original.id)

    assert original == same_id
    assert hash(original) == hash(same_id)
    assert len({original, same_id}) == 1


def test_entities_with_different_ids_are_not_equal(kind: Kind) -> None:
    assert kind.make() != kind.make()


def test_entities_of_different_kinds_are_never_equal() -> None:
    shared_id = uuid4()
    customer = Customer.create(make_customer_details(), NOW, entity_id=shared_id)  # type: ignore[arg-type]
    partner = Partner.create(make_partner_details(), NOW, entity_id=shared_id)  # type: ignore[arg-type]

    assert customer != partner


def test_timestamps_passed_to_constructor_must_be_timezone_aware() -> None:
    with pytest.raises(InvalidValueError):
        Customer(
            id=uuid4(),  # type: ignore[arg-type]
            details=make_customer_details(),
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
