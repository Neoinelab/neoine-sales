"""등록 사용자(owner_user_id): RegisterDeal 저장, 수정·삭제·단계 변경 유지, 파이프라인 mine 인자."""

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
from app.domain.common.errors import InvalidValueError
from app.domain.deal.stage import DealStage
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
async def owned(uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer) -> Deal:
    return await RegisterDeal(uow_factory, clock).execute(
        make_deal_input(customer.id), owner_user_id="u-1"
    )


class TestRegisterDealOwner:
    async def test_stores_the_registering_user_as_owner_user_id(
        self, uow: FakeUnitOfWork, owned: Deal
    ) -> None:
        assert owned.owner_user_id == "u-1"
        assert (await uow.deals.get(owned.id)).owner_user_id == "u-1"

    async def test_without_owner_user_id_it_is_stored_as_none(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))

        assert deal.owner_user_id is None
        assert (await uow.deals.get(deal.id)).owner_user_id is None

    async def test_owner_user_id_is_keyword_only(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        with pytest.raises(TypeError):
            await RegisterDeal(uow_factory, clock).execute(  # type: ignore[call-arg]
                make_deal_input(customer.id), "u-1"
            )

    async def test_too_long_owner_user_id_is_rejected_and_stores_nothing(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
    ) -> None:
        with pytest.raises(InvalidValueError):
            await RegisterDeal(uow_factory, clock).execute(
                make_deal_input(customer.id), owner_user_id="u" * 201
            )

        assert list(await uow.deals.list()) == []

    def test_deal_input_has_no_owner_user_id_field(self, customer: Customer) -> None:
        assert not hasattr(make_deal_input(customer.id), "owner_user_id")


class TestOwnerIsKept:
    async def test_update_keeps_the_owner_user_id(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
        owned: Deal,
    ) -> None:
        updated = await UpdateDeal(uow_factory, clock).execute(
            owned.id, make_deal_input(customer.id, name="이름만 변경")
        )

        assert updated.owner_user_id == "u-1"
        assert (await uow.deals.get(owned.id)).owner_user_id == "u-1"

    async def test_stage_change_keeps_the_owner_user_id(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, owned: Deal
    ) -> None:
        await ChangeDealStage(uow_factory, clock).execute(
            owned.id, make_stage_change_input(stage=DealStage.LOST, reason="예산 부족")
        )

        assert (await uow.deals.get(owned.id)).owner_user_id == "u-1"

    async def test_delete_keeps_the_owner_user_id(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, owned: Deal
    ) -> None:
        await DeleteDeal(uow_factory, clock).execute(owned.id)

        assert (await uow.deals.get(owned.id, include_deleted=True)).owner_user_id == "u-1"


class TestListDealsByOwner:
    async def test_list_deals_with_owner_user_id_returns_only_that_users_deals(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        await register.execute(make_deal_input(customer.id, code="A-1"), owner_user_id="u-1")
        await register.execute(make_deal_input(customer.id, code="B-1"), owner_user_id="u-2")
        await register.execute(make_deal_input(customer.id, code="N-1"))

        mine = await ListDeals(uow_factory).execute(DealQuery(owner_user_id="u-1"))
        everyone = await ListDeals(uow_factory).execute(DealQuery())

        assert [d.details.code.value for d in mine] == ["A-1"]
        assert len(everyone) == 3


class TestGetDealPipelineOwner:
    async def test_pipeline_for_one_owner_user_counts_only_their_deals(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        await register.execute(make_deal_input(customer.id, code="A-1"), owner_user_id="u-1")
        await register.execute(make_deal_input(customer.id, code="A-2"), owner_user_id="u-1")
        await register.execute(make_deal_input(customer.id, code="B-1"), owner_user_id="u-2")
        await register.execute(make_deal_input(customer.id, code="N-1"))

        mine = await GetDealPipeline(uow_factory).execute(owner_user_id="u-1")
        everyone = await GetDealPipeline(uow_factory).execute()

        assert {s.stage: s.deal_count for s in mine.stages}[DealStage.PROSPECTING] == 2
        assert {s.stage: s.deal_count for s in everyone.stages}[DealStage.PROSPECTING] == 4

    async def test_pipeline_for_an_unknown_owner_user_is_empty_but_has_all_stages(
        self, uow_factory: UnitOfWorkFactory, owned: Deal
    ) -> None:
        pipeline = await GetDealPipeline(uow_factory).execute(owner_user_id="nobody")

        assert [s.stage for s in pipeline.stages] == list(DealStage)
        assert all(s.deal_count == 0 for s in pipeline.stages)


class TestGetDealPipelineOwnerNormalization:
    """DealQuery.owner_user_id와 같은 규칙: strip, 공백뿐이면 전체, 200자 초과 거부."""

    async def _count(self, uow_factory: UnitOfWorkFactory, owner_user_id: str) -> int:
        pipeline = await GetDealPipeline(uow_factory).execute(owner_user_id=owner_user_id)
        return {s.stage: s.deal_count for s in pipeline.stages}[DealStage.PROSPECTING]

    async def _two_owners(self, uow_factory: UnitOfWorkFactory, clock: FixedClock) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        register = RegisterDeal(uow_factory, clock)
        await register.execute(make_deal_input(customer.id, code="A-1"), owner_user_id="u-1")
        await register.execute(make_deal_input(customer.id, code="B-1"), owner_user_id="u-2")

    async def test_surrounding_whitespace_is_stripped(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await self._two_owners(uow_factory, clock)

        assert await self._count(uow_factory, "  u-1\t") == 1

    async def test_blank_owner_means_everyone(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await self._two_owners(uow_factory, clock)

        assert await self._count(uow_factory, "   ") == 2

    async def test_owner_over_200_chars_is_rejected(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await self._two_owners(uow_factory, clock)

        with pytest.raises(InvalidValueError):
            await GetDealPipeline(uow_factory).execute(owner_user_id="u" * 201)

    async def test_owner_of_exactly_200_chars_is_accepted(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await self._two_owners(uow_factory, clock)

        assert await self._count(uow_factory, "u" * 200) == 0
