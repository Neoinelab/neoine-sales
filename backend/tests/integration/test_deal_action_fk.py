"""활동 등록과 Deal 삭제의 FK 경계(PostgreSQL): 등록 직전에 Deal이 사라지면 NotFound(500 아님)."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.customer.entities import Customer
from app.domain.deal.entities import Deal
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.value_objects import DealId
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.infra.db.deal_repository import SqlDealRepository
from tests.factories import NOW, make_customer_details, make_deal_action, make_deal_details
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


async def test_add_for_missing_deal_raises_deal_not_found(test_database_url: URL) -> None:
    async with rolled_back_session(test_database_url) as session:
        repository = SqlDealActionRepository(session)

        with pytest.raises(DealNotFoundError):
            await repository.add(make_deal_action(deal_id=DealId(uuid4())))


async def test_add_after_the_deal_is_physically_deleted_raises_deal_not_found(
    test_database_url: URL,
) -> None:
    async with rolled_back_session(test_database_url) as session:
        customer = Customer.create(make_customer_details(), NOW)
        await SqlCustomerRepository(session).add(customer)
        deals = SqlDealRepository(session)
        deal = Deal.create(make_deal_details(customer_id=customer.id), NOW)
        await deals.add(deal)
        await deals.delete(deal.id)

        with pytest.raises(DealNotFoundError):
            await SqlDealActionRepository(session).add(make_deal_action(deal_id=deal.id))
