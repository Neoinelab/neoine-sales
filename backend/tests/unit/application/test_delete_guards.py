"""활성 Deal이 참조하는 고객·파트너는 삭제할 수 없다(삭제된 Deal은 참조로 보지 않는다)."""

from typing import TYPE_CHECKING

import pytest

from app.application.customer.delete_customer import DeleteCustomer
from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.register_deal import RegisterDeal
from app.application.partner.delete_partner import DeletePartner
from app.application.partner.register_partner import RegisterPartner
from app.domain.common.errors import InvalidStateError
from app.domain.customer.errors import CustomerInUseError
from app.domain.partner.errors import PartnerInUseError
from tests.factories import make_customer_input, make_deal_input, make_partner_input

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


class TestDeleteCustomerGuard:
    async def test_customer_with_an_active_deal_cannot_be_deleted(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

        with pytest.raises(CustomerInUseError):
            await DeleteCustomer(uow_factory, clock).execute(customer.id)

        assert not (await uow.customers.get(customer.id)).is_deleted

    async def test_the_error_is_an_invalid_state(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

        with pytest.raises(InvalidStateError):
            await DeleteCustomer(uow_factory, clock).execute(customer.id)

    async def test_customer_can_be_deleted_once_its_deals_are_deleted(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
        await DeleteDeal(uow_factory, clock).execute(deal.id)

        await DeleteCustomer(uow_factory, clock).execute(customer.id)

    async def test_deals_of_other_customers_do_not_block_deletion(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        register = RegisterCustomer(uow_factory, clock)
        free = await register.execute(make_customer_input(company_name="무관"))
        busy = await register.execute(make_customer_input(company_name="거래중"))
        await RegisterDeal(uow_factory, clock).execute(make_deal_input(busy.id))

        await DeleteCustomer(uow_factory, clock).execute(free.id)


class TestDeletePartnerGuard:
    async def test_partner_with_an_active_deal_cannot_be_deleted(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        partner = await RegisterPartner(uow_factory, clock).execute(make_partner_input())
        await RegisterDeal(uow_factory, clock).execute(
            make_deal_input(customer.id, partner_id=partner.id)
        )

        with pytest.raises(PartnerInUseError):
            await DeletePartner(uow_factory, clock).execute(partner.id)

        assert not (await uow.partners.get(partner.id)).is_deleted

    async def test_partner_can_be_deleted_once_its_deals_are_deleted(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        partner = await RegisterPartner(uow_factory, clock).execute(make_partner_input())
        deal = await RegisterDeal(uow_factory, clock).execute(
            make_deal_input(customer.id, partner_id=partner.id)
        )
        await DeleteDeal(uow_factory, clock).execute(deal.id)

        await DeletePartner(uow_factory, clock).execute(partner.id)
