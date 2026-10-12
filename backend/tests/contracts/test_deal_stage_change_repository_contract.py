"""DealStageChangeRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다."""

from contextlib import suppress
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
import pytest_asyncio

from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from app.domain.customer.entities import Customer
from app.domain.deal.entities import Deal
from app.domain.deal.stage import DealStage, DealStageChangeId
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.deal_stage_change_repository import SqlDealStageChangeRepository
from tests.factories import (
    NOW,
    later,
    make_customer_details,
    make_deal_details,
    make_stage_change,
    make_stage_changer,
)
from tests.fakes.stage_change_repository import FakeDealStageChangeRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from app.application.ports.deal_stage_change_repository import DealStageChangeRepository
    from app.domain.deal.stage import DealStageChange
    from app.domain.deal.value_objects import DealId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class Case:
    def __init__(
        self,
        repository: DealStageChangeRepository,
        ensure_deal: Callable[[DealId], Awaitable[None]],
    ) -> None:
        self.repository = repository
        self._ensure_deal = ensure_deal

    async def add(self, change: DealStageChange) -> None:
        await self._ensure_deal(change.deal_id)
        await self.repository.add(change)

    async def search(self, deal_id: DealId, **paging: int) -> list[DealStageChange]:
        return list(await self.repository.search(DealStageChangeQuery(deal_id, **paging)))


async def _nothing(_: DealId) -> None:
    return None


@pytest_asyncio.fixture(params=PARAMS)
async def case(request: pytest.FixtureRequest) -> AsyncIterator[Case]:
    if request.param == "fake":
        yield Case(FakeDealStageChangeRepository(), _nothing)
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        customers, deals = SqlCustomerRepository(session), SqlDealRepository(session)
        customer = Customer.create(make_customer_details(), NOW)
        await customers.add(customer)
        created: set[DealId] = set()

        async def ensure_deal(deal_id: DealId) -> None:
            if deal_id in created:
                return
            created.add(deal_id)
            details = make_deal_details(code=f"D-{len(created)}", customer_id=customer.id)
            with suppress(AlreadyExistsError):
                await deals.add(Deal.create(details, NOW, entity_id=deal_id))

        yield Case(SqlDealStageChangeRepository(session), ensure_deal)


async def test_add_then_search_round_trips_every_field(case: Case) -> None:
    change = make_stage_change(
        from_stage=DealStage.PRICE_NEGOTIATION,
        to_stage=DealStage.LOST,
        reason="예산 부족",
        changed_by=make_stage_changer(subject="u-1", name="김영업"),
        changed_at=later(5),
    )
    await case.add(change)

    (stored,) = await case.search(change.deal_id)

    assert stored == change
    assert stored.changed_at == later(5)


async def test_reason_none_round_trips_as_none(case: Case) -> None:
    change = make_stage_change(reason=None)
    await case.add(change)

    (stored,) = await case.search(change.deal_id)

    assert stored.reason is None


async def test_every_stage_value_can_be_stored_as_from_and_to(case: Case) -> None:
    stages = list(DealStage)
    deal_id = make_stage_change().deal_id
    for number, (src, dst) in enumerate(zip(stages, [*stages[1:], stages[0]], strict=True)):
        await case.add(
            make_stage_change(
                deal_id=deal_id, from_stage=src, to_stage=dst, changed_at=later(number)
            )
        )

    stored = await case.search(deal_id)

    assert len(stored) == len(stages)
    assert {c.to_stage for c in stored} == set(stages)


async def test_add_with_an_existing_id_raises_already_exists(case: Case) -> None:
    change = make_stage_change()
    await case.add(change)

    with pytest.raises(AlreadyExistsError):
        await case.repository.add(change)


async def test_search_orders_latest_first_then_by_id_and_pages(case: Case) -> None:
    deal_id = make_stage_change().deal_id
    low = DealStageChangeId(UUID("00000000-0000-4000-8000-000000000001"))
    high = DealStageChangeId(UUID("00000000-0000-4000-8000-000000000002"))
    oldest = DealStageChangeId(UUID("00000000-0000-4000-8000-000000000000"))
    for change_id, at in ((high, later(10)), (low, later(10)), (oldest, later(1))):
        await case.add(make_stage_change(id=change_id, deal_id=deal_id, changed_at=at))

    found = await case.search(deal_id)

    assert [c.id for c in found] == [low, high, oldest]
    assert [c.id for c in await case.search(deal_id, offset=1, limit=1)] == [high]


async def test_search_returns_only_the_given_deal(case: Case) -> None:
    mine = make_stage_change()
    other = make_stage_change()
    await case.add(mine)
    await case.add(other)

    assert [c.id for c in await case.search(mine.deal_id)] == [mine.id]


async def test_search_of_a_deal_without_history_is_empty(case: Case) -> None:
    assert await case.search(make_stage_change().deal_id) == []


async def test_search_rejects_invalid_paging(case: Case) -> None:
    with pytest.raises(InvalidValueError):
        await case.search(make_stage_change().deal_id, limit=0)
