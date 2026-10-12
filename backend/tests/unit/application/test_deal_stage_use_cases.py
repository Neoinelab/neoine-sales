"""단계 변경·이력 조회·파이프라인 유스케이스(Fake UoW)."""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.change_stage import ChangeDealStage
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_pipeline import GetDealPipeline
from app.application.deal.list_stage_changes import ListDealStageChanges
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import DealId
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


class TestStageOfRegisteredAndUpdatedDeals:
    async def test_registered_deal_starts_at_prospecting(
        self, uow: FakeUnitOfWork, deal: Deal
    ) -> None:
        assert deal.stage is DealStage.PROSPECTING
        assert (await uow.deals.get(deal.id)).stage is DealStage.PROSPECTING

    async def test_update_keeps_the_stage(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        customer: Customer,
        deal: Deal,
    ) -> None:
        await ChangeDealStage(uow_factory, clock).execute(
            deal.id, make_stage_change_input(stage=DealStage.LOST, reason="예산 부족")
        )

        updated = await UpdateDeal(uow_factory, clock).execute(
            deal.id, make_deal_input(customer.id, name="이름만 변경")
        )

        assert updated.stage is DealStage.LOST
        assert (await uow.deals.get(deal.id)).stage is DealStage.LOST


class TestChangeDealStage:
    async def test_saves_deal_and_history_in_one_commit(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        commits_before = uow.commits
        clock.advance(120)

        changed = await ChangeDealStage(uow_factory, clock).execute(
            deal.id, make_stage_change_input(stage=DealStage.POC_PREPARATION, reason="준비")
        )

        assert uow.commits == commits_before + 1
        stored = await uow.deals.get(deal.id)
        assert stored.stage is DealStage.POC_PREPARATION
        assert changed.stage is DealStage.POC_PREPARATION
        assert stored.updated_at == clock.now()
        history = await uow.deal_stage_changes.search(DealStageChangeQuery(deal_id=deal.id))
        assert [(c.from_stage, c.to_stage, c.reason) for c in history] == [
            (DealStage.PROSPECTING, DealStage.POC_PREPARATION, "준비")
        ]
        assert history[0].changed_at == clock.now()

    async def test_failure_leaves_neither_stage_nor_history(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        commits_before = uow.commits

        with pytest.raises(InvalidValueError):
            await ChangeDealStage(uow_factory, clock).execute(
                deal.id, make_stage_change_input(stage=DealStage.LOST, reason=None)
            )

        assert uow.commits == commits_before
        assert (await uow.deals.get(deal.id)).stage is DealStage.PROSPECTING
        assert await uow.deal_stage_changes.search(DealStageChangeQuery(deal_id=deal.id)) == []

    async def test_history_write_failure_rolls_back_the_stage(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        async def broken_add(change: object) -> None:
            raise RuntimeError("이력 저장 실패")

        uow.deal_stage_changes.add = broken_add  # type: ignore[method-assign]

        with pytest.raises(RuntimeError):
            await ChangeDealStage(uow_factory, clock).execute(
                deal.id, make_stage_change_input(stage=DealStage.INTRODUCTION)
            )

        assert (await uow.deals.get(deal.id)).stage is DealStage.PROSPECTING

    async def test_same_stage_raises_invalid_state_and_records_nothing(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        with pytest.raises(InvalidStateError):
            await ChangeDealStage(uow_factory, clock).execute(
                deal.id, make_stage_change_input(stage=DealStage.PROSPECTING)
            )

        assert await uow.deal_stage_changes.search(DealStageChangeQuery(deal_id=deal.id)) == []

    async def test_records_the_given_changer(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        await ChangeDealStage(uow_factory, clock).execute(
            deal.id,
            make_stage_change_input(changed_by_subject="u-9", changed_by_name="최영업"),
        )

        (change,) = await uow.deal_stage_changes.search(DealStageChangeQuery(deal_id=deal.id))
        assert (change.changed_by.subject, change.changed_by.name) == ("u-9", "최영업")

    async def test_can_move_back_and_reopen_a_lost_deal(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        use_case = ChangeDealStage(uow_factory, clock)
        await use_case.execute(
            deal.id, make_stage_change_input(stage=DealStage.LOST, reason="예산")
        )
        clock.advance(10)

        await use_case.execute(deal.id, make_stage_change_input(stage=DealStage.INTRODUCTION))

        assert (await uow.deals.get(deal.id)).stage is DealStage.INTRODUCTION
        history = await uow.deal_stage_changes.search(DealStageChangeQuery(deal_id=deal.id))
        assert [c.to_stage for c in history] == [DealStage.INTRODUCTION, DealStage.LOST]

    async def test_unknown_or_deleted_deal_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        use_case = ChangeDealStage(uow_factory, clock)
        await DeleteDeal(uow_factory, clock).execute(deal.id)

        with pytest.raises(DealNotFoundError):
            await use_case.execute(DealId(uuid4()), make_stage_change_input())
        with pytest.raises(DealNotFoundError):
            await use_case.execute(deal.id, make_stage_change_input())


class TestListDealStageChanges:
    async def test_lists_latest_first(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        change = ChangeDealStage(uow_factory, clock)
        await change.execute(deal.id, make_stage_change_input(stage=DealStage.INTRODUCTION))
        clock.advance(60)
        await change.execute(deal.id, make_stage_change_input(stage=DealStage.POC_PREPARATION))

        found = await ListDealStageChanges(uow_factory).execute(DealStageChangeQuery(deal.id))

        assert [c.to_stage for c in found] == [DealStage.POC_PREPARATION, DealStage.INTRODUCTION]

    async def test_history_of_a_deleted_deal_stays_readable(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        await ChangeDealStage(uow_factory, clock).execute(deal.id, make_stage_change_input())
        await DeleteDeal(uow_factory, clock).execute(deal.id)

        found = await ListDealStageChanges(uow_factory).execute(DealStageChangeQuery(deal.id))

        assert len(found) == 1

    async def test_unknown_deal_raises_not_found(self, uow_factory: UnitOfWorkFactory) -> None:
        with pytest.raises(DealNotFoundError):
            await ListDealStageChanges(uow_factory).execute(DealStageChangeQuery(DealId(uuid4())))

    async def test_pages_with_offset_and_limit(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
    ) -> None:
        change = ChangeDealStage(uow_factory, clock)
        for stage in (DealStage.INTRODUCTION, DealStage.POC_PREPARATION, DealStage.POC_COMPLETED):
            await change.execute(deal.id, make_stage_change_input(stage=stage))
            clock.advance(60)

        found = await ListDealStageChanges(uow_factory).execute(
            DealStageChangeQuery(deal.id, offset=1, limit=1)
        )

        assert [c.to_stage for c in found] == [DealStage.POC_PREPARATION]


class TestStageChangeQuery:
    @pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
    def test_rejects_invalid_paging(self, offset: int, limit: int) -> None:
        with pytest.raises(InvalidValueError):
            DealStageChangeQuery(DealId(uuid4()), offset=offset, limit=limit)


class TestGetDealPipeline:
    async def test_counts_and_sums_by_stage_and_currency(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, customer: Customer
    ) -> None:
        register = RegisterDeal(uow_factory, clock)
        first = await register.execute(make_deal_input(customer.id, code="D-1"))
        await register.execute(make_deal_input(customer.id, code="D-2", revenue_amount=Decimal(50)))
        usd = await register.execute(
            make_deal_input(
                customer.id, code="D-3", revenue_amount=Decimal("5.5"), revenue_currency="USD"
            )
        )
        change = ChangeDealStage(uow_factory, clock)
        await change.execute(first.id, make_stage_change_input(stage=DealStage.LOST, reason="x"))
        await change.execute(usd.id, make_stage_change_input(stage=DealStage.LOST, reason="y"))

        pipeline = await GetDealPipeline(uow_factory).execute()

        by_stage = {s.stage: s for s in pipeline.stages}
        assert by_stage[DealStage.PROSPECTING].deal_count == 1
        assert by_stage[DealStage.LOST].deal_count == 2
        assert [(t.currency, t.amount) for t in by_stage[DealStage.LOST].totals] == [
            ("KRW", Decimal(150000000)),
            ("USD", Decimal("5.5")),
        ]

    async def test_pipeline_has_all_stages_even_without_deals(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        pipeline = await GetDealPipeline(uow_factory).execute()

        assert [s.stage for s in pipeline.stages] == list(DealStage)
        assert all(s.deal_count == 0 for s in pipeline.stages)
