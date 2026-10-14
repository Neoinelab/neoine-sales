"""등록자(registered_by_user_id)와 담당자(owner_user_id)의 구분, 내 딜=담당자 기준 (AC12)."""

from typing import TYPE_CHECKING

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.change_stage import ChangeDealStage
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_pipeline import GetDealPipeline
from app.application.deal.list_deals import ListDeals
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.ports.deal_repository import DealQuery
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.stage import DealStage
from tests.factories import make_customer_input, make_deal_input, make_stage_change_input
from tests.support.user_ids import OWNER_ID, uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.deal.entities import Deal
    from app.domain.user.value_objects import UserId
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

pytestmark = pytest.mark.usefixtures("default_users")


@pytest.fixture
async def customer(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> Customer:
    return await RegisterCustomer(uow_factory, clock).execute(make_customer_input())


@pytest.fixture
async def registered(uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer) -> Deal:
    return await RegisterDeal(uow_factory, clock).execute(
        make_deal_input(customer.id), registered_by_user_id=uid("registrant")
    )


class TestRegisterDealRegistrant:
    async def test_stores_the_registering_user_separately_from_the_owner(
        self, uow: FakeUnitOfWork, registered: Deal
    ) -> None:
        stored = await uow.deals.get(registered.id)

        assert stored.registered_by_user_id == uid("registrant")
        assert stored.details.owner_user_id == OWNER_ID

    async def test_without_registrant_it_is_stored_as_none(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

        assert deal.registered_by_user_id is None
        assert (await uow.deals.get(deal.id)).registered_by_user_id is None

    async def test_registrant_is_keyword_only(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        with pytest.raises(TypeError):
            await RegisterDeal(uow_factory, clock).execute(  # type: ignore[call-arg]
                make_deal_input(customer.id), uid("registrant")
            )

    def test_deal_input_carries_the_owner_but_not_the_registrant(self, customer: Customer) -> None:
        data = make_deal_input(customer.id)

        assert data.owner_user_id == OWNER_ID
        assert not hasattr(data, "registered_by_user_id")
        assert not hasattr(data, "owner")


class TestRegistrantIsKept:
    async def test_update_keeps_the_registrant(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
        registered: Deal,
    ) -> None:
        await UpdateDeal(uow_factory, clock).execute(
            registered.id, make_deal_input(customer.id, name="이름만 변경")
        )

        assert (await uow.deals.get(registered.id)).registered_by_user_id == uid("registrant")

    async def test_stage_change_keeps_the_registrant(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        registered: Deal,
    ) -> None:
        await ChangeDealStage(uow_factory, clock).execute(
            registered.id, make_stage_change_input(stage=DealStage.LOST, reason="예산 부족")
        )

        assert (await uow.deals.get(registered.id)).registered_by_user_id == uid("registrant")

    async def test_delete_removes_the_deal_physically(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        registered: Deal,
    ) -> None:
        await DeleteDeal(uow_factory, clock).execute(registered.id)

        with pytest.raises(DealNotFoundError):
            await uow.deals.get(registered.id)


class TestMineMeansOwner:
    async def _deals(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        mine = uid("me")
        await _seed(uow_factory, mine)
        await register.execute(
            make_deal_input(customer.id, code="OWN-1", owner_user_id=mine),
            registered_by_user_id=uid("other"),
        )
        await register.execute(
            make_deal_input(customer.id, code="REG-1"), registered_by_user_id=mine
        )
        await register.execute(make_deal_input(customer.id, code="NONE-1"))

    async def test_list_by_owner_returns_deals_owned_not_registered_by_the_user(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        await self._deals(uow_factory, clock, customer)

        found = await ListDeals(uow_factory).execute(DealQuery(owner_user_id=uid("me")))

        assert [d.details.code.value for d in found] == ["OWN-1"]

    async def test_without_owner_condition_everyone_is_listed(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        await self._deals(uow_factory, clock, customer)

        assert len(await ListDeals(uow_factory).execute(DealQuery())) == 3

    async def test_pipeline_for_one_owner_counts_deals_by_owner(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        await self._deals(uow_factory, clock, customer)

        mine = await GetDealPipeline(uow_factory).execute(owner_user_id=uid("me"))
        everyone = await GetDealPipeline(uow_factory).execute()

        assert {s.stage: s.deal_count for s in mine.stages}[DealStage.PROSPECTING] == 1
        assert {s.stage: s.deal_count for s in everyone.stages}[DealStage.PROSPECTING] == 3

    async def test_pipeline_for_an_owner_without_deals_has_all_stages_and_zero_counts(
        self, uow_factory: UnitOfWorkFactory, registered: Deal
    ) -> None:
        pipeline = await GetDealPipeline(uow_factory).execute(owner_user_id=uid("nobody"))

        assert [s.stage for s in pipeline.stages] == list(DealStage)
        assert all(s.deal_count == 0 for s in pipeline.stages)


async def _seed(uow_factory: UnitOfWorkFactory, *user_ids: UserId) -> None:
    async with uow_factory() as uow:
        await ensure_users(uow.users, *user_ids)
        await uow.commit()
