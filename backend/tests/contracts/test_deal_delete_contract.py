"""DealRepository.delete 계약: 물리 삭제, 활동·단계 이력(FK RESTRICT)이 있으면 DealInUseError.

Fake(자식 저장소를 연결해 RESTRICT를 모사)와 SQL 구현(실제 PostgreSQL FK)에 같은 테스트를 적용한다.
"""

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.common.errors import AlreadyExistsError
from app.domain.customer.entities import Customer
from app.domain.deal.errors import DealInUseError, DealNotFoundError
from app.domain.deal.value_objects import DealCode
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.deal_stage_change_repository import SqlDealStageChangeRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import (
    NOW,
    make_customer_details,
    make_deal,
    make_deal_action,
    make_stage_change,
)
from tests.fakes.repositories import FakeDealActionRepository, FakeDealRepository
from tests.fakes.stage_change_repository import FakeDealStageChangeRepository
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

    from app.domain.deal.entities import Deal
    from app.domain.deal_action.entities import DealAction

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@dataclass
class DeleteCase:
    deals: Any
    actions: Any
    stage_changes: Any
    users: Any = None
    customer: Customer | None = None

    async def new_deal(self, code: str = "DEAL-001") -> Deal:
        deal = (
            make_deal(code=code, customer_id=self.customer.id)
            if self.customer
            else make_deal(code=code)
        )
        await ensure_users(self.users, deal.details.owner_user_id)  # FK: 담당자 행
        await self.deals.add(deal)
        return deal

    async def add_action(self, deal: Deal) -> DealAction:
        action = make_deal_action(deal_id=deal.id)
        await ensure_users(self.users, action.details.actor_user_id)  # FK: 활동자 행
        await self.actions.add(action)
        return action

    async def add_stage_change(self, deal: Deal) -> None:
        change = make_stage_change(deal_id=deal.id)
        await ensure_users(self.users, change.changed_by.user_id)  # FK: 변경자 행
        await self.stage_changes.add(change)


@pytest_asyncio.fixture(params=PARAMS)
async def delete_case(request: pytest.FixtureRequest) -> AsyncIterator[DeleteCase]:
    if request.param == "fake":
        deals, actions = FakeDealRepository(), FakeDealActionRepository()
        stage_changes = FakeDealStageChangeRepository()
        deals.restrict_delete_by(actions, stage_changes)
        yield DeleteCase(deals, actions, stage_changes, FakeUserRepository())
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        customer = Customer.create(make_customer_details(), NOW)
        with suppress(AlreadyExistsError):
            await SqlCustomerRepository(session).add(customer)
        yield DeleteCase(
            SqlDealRepository(session),
            SqlDealActionRepository(session),
            SqlDealStageChangeRepository(session),
            SqlUserRepository(session),
            customer,
        )


async def test_delete_removes_the_row_physically_and_frees_the_code(
    delete_case: DeleteCase,
) -> None:
    deal = await delete_case.new_deal()

    await delete_case.deals.delete(deal.id)

    with pytest.raises(DealNotFoundError):
        await delete_case.deals.get(deal.id)
    with pytest.raises(DealNotFoundError):
        await delete_case.deals.get_by_code(DealCode("DEAL-001"))
    await delete_case.new_deal("DEAL-001")  # 같은 코드로 다시 등록할 수 있다


async def test_delete_unknown_deal_raises_not_found(delete_case: DeleteCase) -> None:
    with pytest.raises(DealNotFoundError):
        await delete_case.deals.delete(make_deal().id)


async def test_delete_blocked_by_an_action_raises_deal_in_use_and_keeps_both(
    delete_case: DeleteCase,
) -> None:
    deal = await delete_case.new_deal()
    action = await delete_case.add_action(deal)

    with pytest.raises(DealInUseError):
        await delete_case.deals.delete(deal.id)

    assert (await delete_case.deals.get(deal.id)).id == deal.id
    assert (await delete_case.actions.get(action.id)).id == action.id


async def test_delete_blocked_by_a_stage_change_raises_deal_in_use(
    delete_case: DeleteCase,
) -> None:
    deal = await delete_case.new_deal()
    await delete_case.add_stage_change(deal)

    with pytest.raises(DealInUseError):
        await delete_case.deals.delete(deal.id)

    assert (await delete_case.deals.get(deal.id)).id == deal.id
    assert await delete_case.stage_changes.exists_for_deal(deal.id)


async def test_delete_succeeds_once_actions_are_physically_removed(
    delete_case: DeleteCase,
) -> None:
    deal = await delete_case.new_deal()
    action = await delete_case.add_action(deal)
    await delete_case.actions.delete(action.id)

    await delete_case.deals.delete(deal.id)

    with pytest.raises(DealNotFoundError):
        await delete_case.deals.get(deal.id)


async def test_stage_change_exists_for_deal_only_for_the_deal_with_history(
    delete_case: DeleteCase,
) -> None:
    with_history = await delete_case.new_deal("DEAL-001")
    without = await delete_case.new_deal("DEAL-002")
    await delete_case.add_stage_change(with_history)

    assert await delete_case.stage_changes.exists_for_deal(with_history.id)
    assert not await delete_case.stage_changes.exists_for_deal(without.id)
