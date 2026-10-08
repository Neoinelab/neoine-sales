"""딜을 바꾸는 유스케이스는 행을 잠그는 조회(for_update=True)로 딜을 읽는다.

잠그지 않으면 동시에 커밋된 단계 변경을 오래된 값으로 덮어쓴다(리뷰 Major).
Fake는 잠금 자체를 흉내 내지 않고 호출만 기록하므로, 여기서는 "잠금 조회를 요청했는지"를 고정한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.change_stage import ChangeDealStage
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from tests.factories import make_customer_input, make_deal_input, make_stage_change_input

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.deal.entities import Deal
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
async def customer(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> Customer:
    return await RegisterCustomer(uow_factory, clock).execute(make_customer_input())


@pytest.fixture
async def deal(uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer) -> Deal:
    return await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))


async def test_change_stage_reads_the_deal_with_a_row_lock(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    uow.deals.for_update_gets.clear()

    await ChangeDealStage(uow_factory, clock).execute(deal.id, make_stage_change_input())

    assert uow.deals.for_update_gets == [deal.id]


async def test_update_deal_reads_the_deal_with_a_row_lock(
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    customer: Customer,
    deal: Deal,
) -> None:
    uow.deals.for_update_gets.clear()

    await UpdateDeal(uow_factory, clock).execute(deal.id, make_deal_input(customer.id, name="변경"))

    assert uow.deals.for_update_gets == [deal.id]


async def test_delete_deal_reads_the_deal_with_a_row_lock(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    uow.deals.for_update_gets.clear()

    await DeleteDeal(uow_factory, clock).execute(deal.id)

    assert uow.deals.for_update_gets == [deal.id]
