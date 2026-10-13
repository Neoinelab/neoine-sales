"""Deal이 가리키는 고객·파트너가 DB에 없으면 FK 위반이 InvalidReferenceError가 된다(AC7)."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.common.errors import InvalidReferenceError
from app.domain.customer.entities import Customer
from app.domain.customer.value_objects import CustomerId
from app.domain.partner.value_objects import PartnerId
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_repository import SqlDealRepository
from tests.factories import NOW, make_customer_details, make_deal, make_deal_details

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_add_with_a_missing_customer_raises_invalid_reference(session: AsyncSession) -> None:
    deal = make_deal(customer_id=CustomerId(uuid4()))

    with pytest.raises(InvalidReferenceError):
        await SqlDealRepository(session).add(deal)


async def test_add_with_a_missing_partner_raises_invalid_reference(session: AsyncSession) -> None:
    customer = Customer.create(make_customer_details(), NOW)
    await SqlCustomerRepository(session).add(customer)
    deal = make_deal(customer_id=customer.id, partner_id=PartnerId(uuid4()))

    with pytest.raises(InvalidReferenceError):
        await SqlDealRepository(session).add(deal)


async def test_update_to_a_missing_customer_raises_invalid_reference(session: AsyncSession) -> None:
    customer = Customer.create(make_customer_details(), NOW)
    await SqlCustomerRepository(session).add(customer)
    deals = SqlDealRepository(session)
    deal = make_deal(customer_id=customer.id)
    await deals.add(deal)
    deal.update(make_deal_details(code=deal.details.code, customer_id=CustomerId(uuid4())), NOW)

    with pytest.raises(InvalidReferenceError):
        await deals.update(deal)


async def test_update_to_a_missing_partner_raises_invalid_reference(session: AsyncSession) -> None:
    customer = Customer.create(make_customer_details(), NOW)
    await SqlCustomerRepository(session).add(customer)
    deals = SqlDealRepository(session)
    deal = make_deal(customer_id=customer.id)
    await deals.add(deal)
    details = make_deal_details(
        code=deal.details.code, customer_id=customer.id, partner_id=PartnerId(uuid4())
    )
    deal.update(details, NOW)

    with pytest.raises(InvalidReferenceError):
        await deals.update(deal)
