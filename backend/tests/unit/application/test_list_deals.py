"""ListDeals: DealQuery를 받아 삭제되지 않은 Deal을 생성 순서대로 돌려준다(Fake UoW)."""

from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.list_deals import ListDeals
from app.application.deal.register_deal import RegisterDeal
from app.application.ports.deal_repository import DealQuery
from app.domain.customer.value_objects import CustomerId
from tests.factories import make_customer_input, make_deal_input
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from tests.fakes.unit_of_work import FixedClock


pytestmark = pytest.mark.usefixtures("default_users")


@pytest.fixture
async def customer(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> Customer:
    return await RegisterCustomer(uow_factory, clock).execute(make_customer_input())


async def test_list_deals_without_conditions_returns_active_deals_in_creation_order(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
) -> None:
    register = RegisterDeal(uow_factory, clock)
    created = []
    for number in range(3):
        clock.advance()
        created.append(await register.execute(make_deal_input(customer.id, code=f"D-{number}")))
    await DeleteDeal(uow_factory, clock).execute(created[1].id)

    found = await ListDeals(uow_factory).execute(DealQuery())

    assert [d.id for d in found] == [created[0].id, created[2].id]


async def test_list_deals_passes_conditions_to_repository(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
) -> None:
    register = RegisterDeal(uow_factory, clock)
    clock.advance()
    async with uow_factory() as uow:
        await ensure_users(uow.users, uid("park"), uid("manager"))
        await uow.commit()
    await register.execute(make_deal_input(customer.id, code="D-1", owner_user_id=uid("park")))
    clock.advance()
    wanted = await register.execute(
        make_deal_input(customer.id, code="D-2", owner_user_id=uid("manager"))
    )

    found = await ListDeals(uow_factory).execute(DealQuery(owner_user_id=uid("manager")))

    assert [d.id for d in found] == [wanted.id]


async def test_list_deals_applies_revenue_range_and_page_together(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
) -> None:
    register = RegisterDeal(uow_factory, clock)
    created = []
    for number, day in enumerate([date(2026, 5, 31), date(2026, 6, 1), date(2026, 6, 30)]):
        clock.advance()
        deal_input = make_deal_input(customer.id, code=f"D-{number}", revenue_date=day)
        created.append(await register.execute(deal_input))

    query = DealQuery(revenue_from=date(2026, 6, 1), revenue_to=date(2026, 7, 1), offset=1, limit=5)
    found = await ListDeals(uow_factory).execute(query)

    assert [d.id for d in found] == [created[2].id]


async def test_list_deals_with_unknown_customer_returns_empty(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
) -> None:
    await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

    found = await ListDeals(uow_factory).execute(DealQuery(customer_id=CustomerId(uuid4())))

    assert list(found) == []
