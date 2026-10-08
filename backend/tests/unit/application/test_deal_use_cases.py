from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.delete_customer import DeleteCustomer
from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_deal import GetDeal
from app.application.deal.get_deal_by_code import GetDealByCode
from app.application.deal.list_deals import ListDeals
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.partner.delete_partner import DeletePartner
from app.application.partner.register_partner import RegisterPartner
from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidReferenceError, InvalidValueError
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.domain.deal.value_objects import DealId
from tests.factories import make_customer_input, make_deal_input, make_partner_input

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.partner.entities import Partner
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
async def customer(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> Customer:
    return await RegisterCustomer(uow_factory, clock).execute(make_customer_input())


@pytest.fixture
async def partner(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> Partner:
    return await RegisterPartner(uow_factory, clock).execute(make_partner_input())


class TestRegisterDeal:
    async def test_persists_the_deal_and_commits_once(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        commits_before = uow.commits

        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

        assert uow.commits == commits_before + 1
        stored = await uow.deals.get(deal.id)
        assert stored.details.code.value == "DEAL-001"
        assert stored.details.customer_id == customer.id
        assert deal.created_at == clock.now()

    async def test_accepts_an_existing_partner(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
        partner: Partner,
    ) -> None:
        deal = await RegisterDeal(uow_factory, clock).execute(
            make_deal_input(customer.id, partner_id=partner.id)
        )

        assert deal.details.partner_id == partner.id

    async def test_unknown_customer_is_an_invalid_reference_and_stores_nothing(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        with pytest.raises(InvalidReferenceError):
            await RegisterDeal(uow_factory, clock).execute(make_deal_input(uuid4()))

        assert uow.commits == 0
        assert list(await uow.deals.list()) == []

    async def test_deleted_customer_cannot_be_referenced(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        await DeleteCustomer(uow_factory, clock).execute(customer.id)

        with pytest.raises(InvalidReferenceError):
            await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

    async def test_unknown_or_deleted_partner_is_an_invalid_reference(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
        partner: Partner,
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        with pytest.raises(InvalidReferenceError):
            await register.execute(make_deal_input(customer.id, partner_id=uuid4()))

        await DeletePartner(uow_factory, clock).execute(partner.id)
        with pytest.raises(InvalidReferenceError):
            await register.execute(make_deal_input(customer.id, partner_id=partner.id))

    async def test_duplicate_code_is_rejected_and_the_first_deal_is_untouched(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        first = await register.execute(make_deal_input(customer.id))

        with pytest.raises(DuplicateDealCodeError):
            await register.execute(make_deal_input(customer.id, name="다른 딜"))

        assert [d.id for d in await uow.deals.list()] == [first.id]

    async def test_invalid_input_is_rejected_before_anything_is_stored(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        commits_before = uow.commits

        with pytest.raises(InvalidValueError):
            await RegisterDeal(uow_factory, clock).execute(
                make_deal_input(customer.id, revenue_amount=Decimal(-1))
            )

        assert uow.commits == commits_before
        assert list(await uow.deals.list()) == []


class TestReadDeals:
    async def test_get_by_id_and_by_code(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

        assert await GetDeal(uow_factory).execute(deal.id) == deal
        assert await GetDealByCode(uow_factory).execute("Deal-001") == deal

    async def test_unknown_deal_raises_not_found(self, uow_factory: UnitOfWorkFactory) -> None:
        with pytest.raises(DealNotFoundError):
            await GetDeal(uow_factory).execute(DealId(uuid4()))
        with pytest.raises(DealNotFoundError):
            await GetDealByCode(uow_factory).execute("NOPE-1")

    async def test_list_pages_in_creation_order_and_excludes_deleted(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        created = []
        for number in range(4):
            clock.advance()
            created.append(await register.execute(make_deal_input(customer.id, code=f"D-{number}")))
        await DeleteDeal(uow_factory, clock).execute(created[0].id)

        page = await ListDeals(uow_factory).execute(DealQuery(offset=1, limit=2))

        assert [d.id for d in page] == [created[2].id, created[3].id]


class TestUpdateDeal:
    async def test_replaces_details_and_uses_the_clock(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
        clock.advance(300)

        updated = await UpdateDeal(uow_factory, clock).execute(
            deal.id, make_deal_input(customer.id, name="확장 프로젝트", vendor="Oracle")
        )

        stored = await uow.deals.get(deal.id)
        assert stored.details.name == "확장 프로젝트"
        assert stored.details.vendor == "Oracle"
        assert updated.updated_at == clock.now()

    async def test_unknown_customer_leaves_the_deal_unchanged(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

        with pytest.raises(InvalidReferenceError):
            await UpdateDeal(uow_factory, clock).execute(
                deal.id, make_deal_input(uuid4(), name="바뀌면 안 됨")
            )

        assert (await uow.deals.get(deal.id)).details.name == "ERP 구축"

    async def test_code_of_another_deal_is_rejected_and_nothing_changes(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        await register.execute(make_deal_input(customer.id, code="D-1"))
        second = await register.execute(make_deal_input(customer.id, code="D-2"))

        with pytest.raises(DuplicateDealCodeError):
            await UpdateDeal(uow_factory, clock).execute(
                second.id, make_deal_input(customer.id, code="D-1", name="바뀌면 안 됨")
            )

        stored = await uow.deals.get(second.id)
        assert stored.details.code.value == "D-2"
        assert stored.details.name == "ERP 구축"

    async def test_unknown_deal_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        with pytest.raises(DealNotFoundError):
            await UpdateDeal(uow_factory, clock).execute(
                DealId(uuid4()), make_deal_input(customer.id)
            )


class TestDeleteDeal:
    async def test_soft_deletes_and_hides_the_deal(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
        clock.advance(120)

        await DeleteDeal(uow_factory, clock).execute(deal.id)

        with pytest.raises(DealNotFoundError):
            await GetDeal(uow_factory).execute(deal.id)
        assert (await uow.deals.get(deal.id, include_deleted=True)).deleted_at == clock.now()

    async def test_deleted_deal_code_cannot_be_reused(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        deal = await register.execute(make_deal_input(customer.id))
        await DeleteDeal(uow_factory, clock).execute(deal.id)

        with pytest.raises(DuplicateDealCodeError):
            await register.execute(make_deal_input(customer.id))

    async def test_unknown_or_already_deleted_deal_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        with pytest.raises(DealNotFoundError):
            await DeleteDeal(uow_factory, clock).execute(DealId(uuid4()))
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
        await DeleteDeal(uow_factory, clock).execute(deal.id)

        with pytest.raises(DealNotFoundError):
            await DeleteDeal(uow_factory, clock).execute(deal.id)
