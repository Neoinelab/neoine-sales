"""Fake가 Port(Protocol)와 시그니처까지 일치하는지 mypy가 정적으로 검증하게 한다.

계약 테스트는 repository를 느슨한 타입으로 다루므로, 이 대입문이 Port 호환성의 안전망이다.
"""

from typing import TYPE_CHECKING

from tests.fakes.repositories import (
    FakeCustomerRepository,
    FakeDealRepository,
    FakePartnerRepository,
)

if TYPE_CHECKING:
    from app.application.ports.customer_repository import CustomerRepository
    from app.application.ports.deal_repository import DealRepository
    from app.application.ports.partner_repository import PartnerRepository


def test_fakes_satisfy_their_ports() -> None:
    customers: CustomerRepository = FakeCustomerRepository()
    partners: PartnerRepository = FakePartnerRepository()
    deals: DealRepository = FakeDealRepository()

    assert customers is not None
    assert partners is not None
    assert deals is not None
