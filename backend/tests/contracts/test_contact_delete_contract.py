"""Customer/PartnerRepository.delete 계약(AC7): 참조하는 Deal이 있으면 InUseError, 없으면 물리 삭제.

Fake(restrict_delete_by로 FK RESTRICT 모사)와 SQL 구현(실제 PostgreSQL FK)에 같은 테스트를 적용한다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from app.domain.customer.entities import Customer
from app.domain.customer.errors import CustomerInUseError, CustomerNotFoundError
from app.domain.partner.entities import Partner
from app.domain.partner.errors import PartnerInUseError, PartnerNotFoundError
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.partner_repository import SqlPartnerRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, make_customer_details, make_deal, make_partner_details
from tests.fakes.repositories import (
    FakeCustomerRepository,
    FakeDealRepository,
    FakePartnerRepository,
)
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

PARAMS = [
    pytest.param(
        (kind, impl), id=f"{kind}-{impl}", marks=[pytest.mark.integration] if impl == "sql" else []
    )
    for kind in ("customer", "partner")
    for impl in ("fake", "sql")
]


@dataclass
class ContactDeleteCase:
    kind: str
    customers: Any
    partners: Any
    deals: Any
    in_use: type[Exception]
    not_found: type[Exception]
    users: Any

    @property
    def contacts(self) -> Any:  # noqa: ANN401 - 고객·파트너 저장소 공용 접근자
        return self.customers if self.kind == "customer" else self.partners

    async def new_contact_with_deal(self) -> Customer | Partner:
        """연락처(고객 또는 파트너)와, 그것을 참조하는 Deal 1건을 만든다."""
        customer = Customer.create(make_customer_details(), NOW)
        await self.customers.add(customer)
        partner = Partner.create(make_partner_details(), NOW)
        await self.partners.add(partner)
        deal = make_deal(customer_id=customer.id, partner_id=partner.id)
        await ensure_users(self.users, deal.details.owner_user_id)  # FK: 담당자 행
        await self.deals.add(deal)
        return customer if self.kind == "customer" else partner

    async def new_contact(self) -> Customer | Partner:
        entity = (
            Customer.create(make_customer_details(), NOW)
            if self.kind == "customer"
            else Partner.create(make_partner_details(), NOW)
        )
        await self.contacts.add(entity)
        return entity


@pytest_asyncio.fixture(params=PARAMS)
async def contact_delete_case(request: pytest.FixtureRequest) -> AsyncIterator[ContactDeleteCase]:
    kind, impl = request.param
    in_use = CustomerInUseError if kind == "customer" else PartnerInUseError
    not_found = CustomerNotFoundError if kind == "customer" else PartnerNotFoundError
    if impl == "fake":
        customers, partners, deals = (
            FakeCustomerRepository(),
            FakePartnerRepository(),
            FakeDealRepository(),
        )
        customers.restrict_delete_by(deals)
        partners.restrict_delete_by(deals)
        yield ContactDeleteCase(
            kind, customers, partners, deals, in_use, not_found, FakeUserRepository()
        )
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield ContactDeleteCase(
            kind,
            SqlCustomerRepository(session),
            SqlPartnerRepository(session),
            SqlDealRepository(session),
            in_use,
            not_found,
            SqlUserRepository(session),
        )


async def test_delete_of_a_contact_without_deals_removes_the_row(
    contact_delete_case: ContactDeleteCase,
) -> None:
    entity = await contact_delete_case.new_contact()

    await contact_delete_case.contacts.delete(entity.id)

    with pytest.raises(contact_delete_case.not_found):
        await contact_delete_case.contacts.get(entity.id)


async def test_delete_of_a_referenced_contact_raises_in_use_and_keeps_the_row(
    contact_delete_case: ContactDeleteCase,
) -> None:
    entity = await contact_delete_case.new_contact_with_deal()

    with pytest.raises(contact_delete_case.in_use):
        await contact_delete_case.contacts.delete(entity.id)

    assert (await contact_delete_case.contacts.get(entity.id)).id == entity.id


async def test_delete_succeeds_once_the_referencing_deal_is_deleted(
    contact_delete_case: ContactDeleteCase,
) -> None:
    entity = await contact_delete_case.new_contact_with_deal()
    deal = (await contact_delete_case.deals.list())[0]
    await contact_delete_case.deals.delete(deal.id)

    await contact_delete_case.contacts.delete(entity.id)

    with pytest.raises(contact_delete_case.not_found):
        await contact_delete_case.contacts.get(entity.id)
