"""Deal 삭제와 활동 등록이 겹쳐도 어느 한쪽만 성공하고 고아 행이 없다(AC13).

가드(exists_for_deal) 뒤에 활동이 들어오는 경쟁은 FK RESTRICT가 최종 방어선이다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.deal.delete_deal import DeleteDeal
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.deal.errors import DealInUseError, DealNotFoundError
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import later, make_customer, make_deal, make_deal_action_input
from tests.fakes.unit_of_work import FixedClock
from tests.support.gated_uow import gated

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal

pytestmark = pytest.mark.integration

SETTLE = 0.7  # 겹친 쪽이 DB 잠금에서 기다리게 두는 시간


@pytest_asyncio.fixture
async def uow_factory(test_database_url: URL) -> AsyncIterator[UnitOfWorkFactory]:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await connection.execute(
                text("truncate deal_actions, deal_stage_changes, deals, customers cascade")
            )
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def deal(uow_factory: UnitOfWorkFactory) -> Deal:
    customer = make_customer()
    created = make_deal(customer_id=customer.id)
    async with uow_factory() as setup:
        await setup.customers.add(customer)
        await setup.deals.add(created)
        await setup.commit()
    return created


async def _state(uow_factory: UnitOfWorkFactory, deal: Deal) -> tuple[bool, int]:
    """(Deal 행이 있는가, 이 Deal의 활동 수)."""
    async with uow_factory() as check:
        actions = await check.deal_actions.search(DealActionQuery())
        try:
            await check.deals.get(deal.id, include_deleted=True)
        except DealNotFoundError:
            return False, len(actions)
        return True, len(actions)


async def test_action_registered_while_delete_is_past_its_guard_fails_with_not_found(
    uow_factory: UnitOfWorkFactory, deal: Deal
) -> None:
    """삭제가 행을 잠그고 DELETE 직전에 멈춘 동안 등록을 시작하면, 등록은 DealNotFoundError."""
    reached, release = asyncio.Event(), asyncio.Event()
    delete_factory = gated(
        uow_factory, attribute="deals", method="delete", reached=reached, release=release
    )
    delete_use_case = DeleteDeal(delete_factory, FixedClock(later(60)))
    delete = asyncio.create_task(delete_use_case.execute(deal.id))
    await asyncio.wait_for(reached.wait(), timeout=10)
    register = asyncio.create_task(
        RegisterDealAction(uow_factory, FixedClock(later(61))).execute(
            deal.id, make_deal_action_input()
        )
    )
    await asyncio.sleep(SETTLE)
    release.set()

    outcomes = await asyncio.wait_for(
        asyncio.gather(delete, register, return_exceptions=True), timeout=15
    )

    assert outcomes[0] is None
    assert isinstance(outcomes[1], DealNotFoundError)
    assert await _state(uow_factory, deal) == (False, 0)


async def test_delete_after_an_action_commits_during_its_guard_wait_is_rejected(
    uow_factory: UnitOfWorkFactory, deal: Deal
) -> None:
    """활동 등록이 커밋 직전에 멈춘 동안 시작한 삭제는 등록 커밋 뒤 가드에서 DealInUseError."""
    reached, release = asyncio.Event(), asyncio.Event()
    register_factory = gated(
        uow_factory, attribute="", method="commit", reached=reached, release=release
    )
    register = asyncio.create_task(
        RegisterDealAction(register_factory, FixedClock(later(60))).execute(
            deal.id, make_deal_action_input()
        )
    )
    await asyncio.wait_for(reached.wait(), timeout=10)
    delete = asyncio.create_task(DeleteDeal(uow_factory, FixedClock(later(61))).execute(deal.id))
    await asyncio.sleep(SETTLE)
    release.set()

    outcomes = await asyncio.wait_for(
        asyncio.gather(register, delete, return_exceptions=True), timeout=15
    )

    assert not isinstance(outcomes[0], BaseException)
    assert isinstance(outcomes[1], DealInUseError)
    assert await _state(uow_factory, deal) == (True, 1)
