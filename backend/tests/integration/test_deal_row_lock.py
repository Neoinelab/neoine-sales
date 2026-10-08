"""get(for_update=True)가 실제 PostgreSQL에서 행을 잠가 동시 단계 변경이 직렬화되는지 확인한다."""

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
from app.domain.deal.stage import DealStage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import later, make_customer, make_deal, make_stage_changer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.unit_of_work import UnitOfWorkFactory

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def uow_factory(test_database_url: URL) -> AsyncIterator[UnitOfWorkFactory]:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await connection.execute(text("truncate deal_stage_changes, deals, customers cascade"))
    finally:
        await engine.dispose()


async def test_second_locking_read_waits_until_the_first_unit_commits(
    uow_factory: UnitOfWorkFactory,
) -> None:
    customer = make_customer()
    deal = make_deal(customer_id=customer.id)
    async with uow_factory() as setup:
        await setup.customers.add(customer)
        await setup.deals.add(deal)
        await setup.commit()

    async def change(to: DealStage, at: int) -> None:
        async with uow_factory() as uow:
            current = await uow.deals.get(deal.id, for_update=True)
            record = current.change_stage(
                to, reason=None, changed_by=make_stage_changer(), now=later(at)
            )
            await uow.deals.update(current)
            await uow.deal_stage_changes.add(record)
            await uow.commit()

    async with uow_factory() as first:
        await first.deals.get(deal.id, for_update=True)
        second = asyncio.create_task(change(DealStage.POC_PREPARATION, 20))
        await asyncio.sleep(0.5)
        assert not second.done(), "첫 단위가 행을 잠그고 있는 동안 두 번째가 진행되면 안 된다"
        current = await first.deals.get(deal.id, for_update=True)
        record = current.change_stage(
            DealStage.INTRODUCTION, reason=None, changed_by=make_stage_changer(), now=later(10)
        )
        await first.deals.update(current)
        await first.deal_stage_changes.add(record)
        await first.commit()

    await asyncio.wait_for(second, timeout=10)

    async with uow_factory() as check:
        history = await check.deal_stage_changes.search(DealStageChangeQuery(deal.id))
        stored = await check.deals.get(deal.id)
    assert [(c.from_stage, c.to_stage) for c in history] == [
        (DealStage.INTRODUCTION, DealStage.POC_PREPARATION),
        (DealStage.PROSPECTING, DealStage.INTRODUCTION),
    ]
    assert stored.stage is DealStage.POC_PREPARATION
