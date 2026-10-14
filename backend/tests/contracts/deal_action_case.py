"""DealActionRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽)."""

from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.common.errors import AlreadyExistsError
from app.domain.customer.entities import Customer
from app.domain.deal.entities import Deal
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.value_objects import DealActionId
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, make_customer_details, make_deal_action_details, make_deal_details
from tests.fakes.repositories import FakeDealActionRepository
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from sqlalchemy.engine import URL

    from app.application.ports.deal_action_repository import DealActionRepository
    from app.application.ports.user_repository import UserRepository
    from app.domain.deal.value_objects import DealId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class Case:
    def __init__(
        self,
        repository: DealActionRepository,
        ensure_deal: Callable[[DealId], Awaitable[None]],
        users: UserRepository,
    ) -> None:
        self.repository = repository
        self.users = users
        self._ensure_deal = ensure_deal

    async def add(self, action: DealAction) -> None:
        await self._ensure_deal(action.details.deal_id)
        await ensure_users(self.users, action.details.actor_user_id)  # FK: 활동자 행
        await self.repository.add(action)

    async def add_legacy(self, **overrides: object) -> DealAction:
        """next_action·due_date가 NULL인 기존 행(읽기로만 존재할 수 있다)."""
        details = make_deal_action_details(next_action=None, due_date=None, **overrides)
        legacy = DealAction(
            id=DealActionId(uuid4()), details=details, created_at=NOW, updated_at=NOW
        )
        await self.add(legacy)
        return legacy

    async def search(self, **criteria: object) -> list[str]:
        found = await self.repository.search(DealActionQuery(**criteria))  # type: ignore[arg-type]
        return [a.details.action for a in found]


async def _nothing(_: DealId) -> None:
    return None


@asynccontextmanager
async def open_case(implementation: str, test_database_url: URL | None) -> AsyncIterator[Case]:
    if implementation == "fake":
        yield Case(FakeDealActionRepository(), _nothing, FakeUserRepository())
        return
    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        customers, deals = SqlCustomerRepository(session), SqlDealRepository(session)
        users = SqlUserRepository(session)
        customer = Customer.create(make_customer_details(), NOW)
        await customers.add(customer)
        created: set[DealId] = set()

        async def ensure_deal(deal_id: DealId) -> None:
            if deal_id in created:
                return
            created.add(deal_id)
            details = make_deal_details(code=f"D-{len(created)}", customer_id=customer.id)
            await ensure_users(users, details.owner_user_id)  # FK: 담당자 행
            with suppress(AlreadyExistsError):
                await deals.add(Deal.create(details, NOW, entity_id=deal_id))

        yield Case(SqlDealActionRepository(session), ensure_deal, users)
