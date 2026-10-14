"""단계 변경이 커밋되는 도중 PUT·DELETE가 겹쳐도 deals.stage가 마지막 이력의 to_stage와 같아야 한다.

결정적으로 재현하는 방법: 단계 변경 트랜잭션을 커밋 직전에 멈춰 둔 채 UpdateDeal/DeleteDeal을
시작하고, 그 유스케이스가 deals.update 직전에 멈추게 한다. 단계 변경이 커밋된 뒤 update를 재개하면
잠금 없는 구현은 오래된 stage를 덮어쓴다. 잠금을 쓰면 읽기가 단계 변경 커밋까지
기다려 최신 stage를 본다.
"""

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.deal.change_stage import ChangeDealStage
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
from app.domain.deal.errors import DealInUseError
from app.domain.deal.stage import DealStage
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import (
    later,
    make_customer,
    make_deal,
    make_deal_input,
    make_stage_change_input,
)
from tests.fakes.unit_of_work import FixedClock
from tests.support.gated_uow import gated
from tests.support.user_ids import CHANGER_ID, OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine

    from sqlalchemy.engine import URL

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.deal.entities import Deal

pytestmark = pytest.mark.integration

WAIT = 0.7  # 잠금 없는 구현이 update 직전에 도달하기를 기다리는 시간


@pytest_asyncio.fixture
async def uow_factory(test_database_url: URL) -> AsyncIterator[UnitOfWorkFactory]:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await connection.execute(text("truncate deal_stage_changes, deals, customers cascade"))
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def seeded(uow_factory: UnitOfWorkFactory) -> tuple[Customer, Deal]:
    customer = make_customer()
    deal = make_deal(customer_id=customer.id)
    async with uow_factory() as setup:
        await ensure_users(setup.users, OWNER_ID, CHANGER_ID)  # FK: 담당자·단계 변경자
        await setup.customers.add(customer)
        await setup.deals.add(deal)
        await setup.commit()
    return customer, deal


async def _run_overlap(
    uow_factory: UnitOfWorkFactory,
    deal: Deal,
    other: Callable[[UnitOfWorkFactory], Coroutine[Any, Any, None]],
    *,
    gate_method: str = "update",
) -> Exception | None:
    """단계 변경(prospecting→lost)이 커밋 직전에 멈춘 동안 other를 시작하고 둘 다 끝낸다.

    other가 던진 예외는 호출자가 판정하도록 돌려준다(없으면 None).
    """
    clock = FixedClock(later(60))
    stage_at_commit, release_commit = asyncio.Event(), asyncio.Event()
    other_at_update, release_update = asyncio.Event(), asyncio.Event()

    change_factory = gated(
        uow_factory, attribute="", method="commit", reached=stage_at_commit, release=release_commit
    )
    other_factory = gated(
        uow_factory,
        attribute="deals",
        method=gate_method,
        reached=other_at_update,
        release=release_update,
    )

    change = asyncio.create_task(
        ChangeDealStage(change_factory, clock).execute(
            deal.id, make_stage_change_input(stage=DealStage.LOST, reason="예산 부족")
        )
    )
    await asyncio.wait_for(stage_at_commit.wait(), timeout=10)
    overlapping = asyncio.create_task(other(other_factory))
    # 잠금이 없으면 update 직전에 도달하고, 잠금을 쓰면 단계 변경 커밋까지 읽기에서 기다린다
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(other_at_update.wait(), timeout=WAIT)
    release_commit.set()
    await asyncio.wait_for(change, timeout=10)
    release_update.set()
    try:
        await asyncio.wait_for(overlapping, timeout=10)
    except Exception as error:
        return error
    return None


async def _assert_stage_matches_last_history(uow_factory: UnitOfWorkFactory, deal: Deal) -> None:
    async with uow_factory() as check:
        history = await check.deal_stage_changes.search(DealStageChangeQuery(deal.id))
        stored = await check.deals.get(deal.id)
    assert [(c.from_stage, c.to_stage) for c in history] == [
        (DealStage.PROSPECTING, DealStage.LOST)
    ]
    assert stored.stage is history[0].to_stage, "deals.stage가 마지막 이력의 to_stage와 다르다"


async def test_put_overlapping_a_stage_change_keeps_the_new_stage(
    uow_factory: UnitOfWorkFactory, seeded: tuple[Customer, Deal]
) -> None:
    customer, deal = seeded

    async def put(factory: UnitOfWorkFactory) -> None:
        await UpdateDeal(factory, FixedClock(later(60))).execute(
            deal.id, make_deal_input(customer.id, name="동시 수정")
        )

    assert await _run_overlap(uow_factory, deal, put) is None

    await _assert_stage_matches_last_history(uow_factory, deal)


async def test_delete_overlapping_a_stage_change_is_rejected_and_keeps_the_new_stage(
    uow_factory: UnitOfWorkFactory, seeded: tuple[Customer, Deal]
) -> None:
    """단계 변경이 먼저 행을 잡았으므로 삭제는 커밋된 단계 이력을 보고 DealInUseError가 된다."""
    _, deal = seeded

    async def delete(factory: UnitOfWorkFactory) -> None:
        await DeleteDeal(factory, FixedClock(later(60))).execute(deal.id)

    error = await _run_overlap(uow_factory, deal, delete, gate_method="delete")

    assert isinstance(error, DealInUseError)
    await _assert_stage_matches_last_history(uow_factory, deal)
