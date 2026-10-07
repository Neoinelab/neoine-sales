"""DealActionRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다."""

from contextlib import suppress
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from app.domain.customer.entities import Customer
from app.domain.deal.entities import Deal
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.deal_action.value_objects import ActionType
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.infra.db.deal_repository import SqlDealRepository
from tests.factories import (
    NOW,
    later,
    make_customer_details,
    make_deal_action,
    make_deal_action_details,
    make_deal_details,
)
from tests.fakes.repositories import FakeDealActionRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from app.application.ports.deal_action_repository import DealActionRepository
    from app.domain.deal.value_objects import DealId
    from app.domain.deal_action.entities import DealAction

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class Case:
    def __init__(
        self,
        repository: DealActionRepository,
        ensure_deal: Callable[[DealId], Awaitable[None]],
    ) -> None:
        self.repository = repository
        self._ensure_deal = ensure_deal

    async def add(self, action: DealAction) -> None:
        await self._ensure_deal(action.details.deal_id)
        await self.repository.add(action)

    async def search(self, **criteria: object) -> list[str]:
        found = await self.repository.search(DealActionQuery(**criteria))  # type: ignore[arg-type]
        return [a.details.title for a in found]


async def _nothing(_: DealId) -> None:
    return None


@pytest_asyncio.fixture(params=PARAMS)
async def case(request: pytest.FixtureRequest) -> AsyncIterator[Case]:
    if request.param == "fake":
        yield Case(FakeDealActionRepository(), _nothing)
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

        yield Case(SqlDealActionRepository(session), ensure_deal)


async def test_add_then_get_round_trips_every_field(case: Case) -> None:
    action = make_deal_action(later(5), content="내용")
    await case.add(action)

    stored = await case.repository.get(action.id)

    assert stored == action
    assert stored.details == action.details
    assert stored.created_at == action.created_at


async def test_add_with_an_existing_id_raises_already_exists(case: Case) -> None:
    action = make_deal_action()
    await case.add(action)

    with pytest.raises(AlreadyExistsError):
        await case.repository.add(action)


async def test_get_unknown_action_raises_not_found(case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await case.repository.get(make_deal_action().id)


async def test_update_persists_changes(case: Case) -> None:
    action = make_deal_action()
    await case.add(action)
    action.update(
        make_deal_action_details(deal_id=action.details.deal_id, title="변경", content="c"),
        later(10),
    )

    await case.repository.update(action)

    stored = await case.repository.get(action.id)
    assert stored.details.title == "변경"
    assert stored.updated_at == later(10)


async def test_update_unknown_action_raises_not_found(case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await case.repository.update(make_deal_action())


async def test_soft_deleted_actions_are_hidden_unless_requested(case: Case) -> None:
    action = make_deal_action()
    await case.add(action)
    action.soft_delete(later(10))
    await case.repository.update(action)

    with pytest.raises(DealActionNotFoundError):
        await case.repository.get(action.id)
    assert (await case.repository.get(action.id, include_deleted=True)).is_deleted
    assert await case.search() == []


async def _seed(case: Case) -> None:
    rows = [
        (ActionType.CALL, "첫 통화", "예산 문의 100%", "김영업", 0),
        (ActionType.MEETING, "킥오프 미팅", "요구사항", "박영업", 1),
        (ActionType.MEETING, "최종 미팅", "계약 조건", "김영업", 2),
    ]
    for action_type, title, content, actor, day in rows:
        await case.add(
            make_deal_action(
                later(day),
                action_type=action_type,
                title=title,
                content=content,
                actor=actor,
                acted_at=NOW + timedelta(days=day),
            )
        )


async def test_search_orders_by_latest_activity_first(case: Case) -> None:
    await _seed(case)

    assert await case.search() == ["최종 미팅", "킥오프 미팅", "첫 통화"]


async def test_search_filters(case: Case) -> None:
    await _seed(case)

    assert await case.search(action_type=ActionType.MEETING, actor="김영업") == ["최종 미팅"]
    assert await case.search(keyword="KICKOFF") == []
    assert await case.search(keyword="요구") == ["킥오프 미팅"]
    assert await case.search(keyword="100%") == ["첫 통화"]
    assert await case.search(keyword="_") == []


async def test_search_by_deal_and_period_and_paging(case: Case) -> None:
    await _seed(case)
    other = make_deal_action(title="다른 딜", acted_at=NOW + timedelta(days=5))
    await case.add(other)

    assert await case.search(deal_id=other.details.deal_id) == ["다른 딜"]
    assert await case.search(
        acted_from=NOW + timedelta(days=1), acted_to=NOW + timedelta(days=5)
    ) == ["최종 미팅", "킥오프 미팅"]
    assert await case.search(offset=1, limit=2) == ["최종 미팅", "킥오프 미팅"]


async def test_search_rejects_invalid_criteria(case: Case) -> None:
    with pytest.raises(InvalidValueError):
        await case.search(limit=0)
