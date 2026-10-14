"""UnitOfWork 공통 계약: commit한 변경만 남고, 미커밋·예외·commit 이후의 변경은 사라진다.

Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다. SQL 구현은 실제로 commit하므로
테스트가 끝나면 테이블을 비워 다른 테스트에 영향을 주지 않는다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
from app.domain.customer.errors import CustomerNotFoundError
from app.domain.deal.stage import DealStage
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import later, make_customer, make_deal, make_stage_changer
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.user_ids import CHANGER_ID, OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.deal.value_objects import DealId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def uow_factory(request: pytest.FixtureRequest) -> AsyncIterator[UnitOfWorkFactory]:
    if request.param == "fake":
        shared = FakeUnitOfWork()
        yield lambda: shared
        return
    url = request.getfixturevalue("test_database_url")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await connection.execute(
                text("truncate users, auth_sessions, deals, customers, partners cascade")
            )
    finally:
        await engine.dispose()


async def test_committed_changes_are_visible_to_later_units(
    uow_factory: UnitOfWorkFactory,
) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)
        await uow.commit()

    async with uow_factory() as later_uow:
        assert await later_uow.customers.get(customer.id) == customer


async def test_changes_are_visible_inside_the_unit_before_commit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)

        assert await uow.customers.get(customer.id) == customer


async def test_changes_without_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)

    async with uow_factory() as later_uow:
        with pytest.raises(CustomerNotFoundError):
            await later_uow.customers.get(customer.id)


async def _add_then_fail(uow_factory: UnitOfWorkFactory, customer: Customer) -> None:
    async with uow_factory() as uow:
        await uow.customers.add(customer)
        raise RuntimeError("boom")


async def test_an_exception_discards_changes_even_after_add(uow_factory: UnitOfWorkFactory) -> None:
    customer = make_customer()
    with pytest.raises(RuntimeError, match="boom"):
        await _add_then_fail(uow_factory, customer)

    async with uow_factory() as later_uow:
        with pytest.raises(CustomerNotFoundError):
            await later_uow.customers.get(customer.id)


async def test_explicit_rollback_discards_changes(uow_factory: UnitOfWorkFactory) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)
        await uow.rollback()

        with pytest.raises(CustomerNotFoundError):
            await uow.customers.get(customer.id)


async def test_changes_made_after_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    kept, dropped = make_customer(company_name="유지"), make_customer(company_name="폐기")
    async with uow_factory() as uow:
        await uow.customers.add(kept)
        await uow.commit()
        await uow.customers.add(dropped)

    async with uow_factory() as later_uow:
        assert await later_uow.customers.get(kept.id) == kept
        with pytest.raises(CustomerNotFoundError):
            await later_uow.customers.get(dropped.id)


async def _stage_state(uow_factory: UnitOfWorkFactory, deal_id: DealId) -> tuple[DealStage, int]:
    async with uow_factory() as uow:
        deal = await uow.deals.get(deal_id)
        history = await uow.deal_stage_changes.search(DealStageChangeQuery(deal.id))
        return deal.stage, len(history)


async def _seed_deal(uow_factory: UnitOfWorkFactory) -> DealId:
    customer = make_customer()
    deal = make_deal(customer_id=customer.id)
    async with uow_factory() as uow:
        await ensure_users(uow.users, OWNER_ID, CHANGER_ID)  # FK: 담당자·단계 변경자
        await uow.customers.add(customer)
        await uow.deals.add(deal)
        await uow.commit()
    return deal.id


async def _change_stage(uow_factory: UnitOfWorkFactory, deal_id: DealId, *, commit: bool) -> None:
    async with uow_factory() as uow:
        deal = await uow.deals.get(deal_id, for_update=True)
        change = deal.change_stage(
            DealStage.INTRODUCTION, reason=None, changed_by=make_stage_changer(), now=later(5)
        )
        await uow.deals.update(deal)
        await uow.deal_stage_changes.add(change)
        if commit:
            await uow.commit()


async def test_stage_and_history_are_committed_together(uow_factory: UnitOfWorkFactory) -> None:
    deal_id = await _seed_deal(uow_factory)

    await _change_stage(uow_factory, deal_id, commit=True)

    assert await _stage_state(uow_factory, deal_id) == (DealStage.INTRODUCTION, 1)


async def test_stage_and_history_are_discarded_together_without_commit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    deal_id = await _seed_deal(uow_factory)

    await _change_stage(uow_factory, deal_id, commit=False)

    assert await _stage_state(uow_factory, deal_id) == (DealStage.PROSPECTING, 0)
