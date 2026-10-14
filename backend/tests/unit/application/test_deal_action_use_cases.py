from datetime import date, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.register_deal import RegisterDeal
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.search_deal_actions import SearchDealActions
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.deal_action.value_objects import ActionType, DealActionId
from tests.factories import (
    NOW,
    make_customer_input,
    make_deal_action_input,
    make_deal_input,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


pytestmark = pytest.mark.usefixtures("default_users")


@pytest.fixture
async def deal_id(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> DealId:
    customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
    deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
    return deal.id


class TestRegisterDealAction:
    async def test_stores_the_action_under_the_deal(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        deal_id: DealId,
    ) -> None:
        action = await RegisterDealAction(uow_factory, clock).execute(
            deal_id,
            make_deal_action_input(
                action="  제안서 전달 ",
                next_action=" 견적 회신 ",
                due_date=date(2026, 2, 3),
                memo=" 메모 ",
            ),
        )

        stored = await uow.deal_actions.get(action.id)
        assert stored.details.deal_id == deal_id
        assert stored.details.action == "제안서 전달"
        assert stored.details.next_action == "견적 회신"
        assert stored.details.due_date == date(2026, 2, 3)
        assert stored.details.memo == "메모"
        assert stored.created_at == clock.now()

    async def test_unknown_deal_raises_not_found_and_stores_nothing(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        with pytest.raises(DealNotFoundError):
            await RegisterDealAction(uow_factory, clock).execute(
                DealId(uuid4()), make_deal_action_input()
            )

        assert await uow.deal_actions.search(DealActionQuery()) == []

    async def test_physically_deleted_deal_cannot_receive_actions(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        await DeleteDeal(uow_factory, clock).execute(deal_id)

        with pytest.raises(DealNotFoundError):
            await RegisterDealAction(uow_factory, clock).execute(deal_id, make_deal_action_input())

    async def test_invalid_input_raises_before_any_write(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        deal_id: DealId,
    ) -> None:
        commits = uow.commits

        with pytest.raises(InvalidValueError):
            await RegisterDealAction(uow_factory, clock).execute(
                deal_id, make_deal_action_input(action=" ")
            )

        assert uow.commits == commits

    async def test_one_deal_has_many_actions_listed_latest_first(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        register = RegisterDealAction(uow_factory, clock)
        for day, name in ((1, "첫째"), (3, "셋째"), (2, "둘째")):
            await register.execute(
                deal_id,
                make_deal_action_input(action=name, acted_at=NOW + timedelta(days=day)),
            )

        found = await SearchDealActions(uow_factory).execute(DealActionQuery(deal_id=deal_id))

        assert [a.details.action for a in found] == ["셋째", "둘째", "첫째"]


class TestGetUpdateDelete:
    async def test_get_returns_the_action(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        created = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input()
        )

        assert (await GetDealAction(uow_factory).execute(created.id)) == created

    async def test_get_unknown_action_raises_not_found(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with pytest.raises(DealActionNotFoundError):
            await GetDealAction(uow_factory).execute(DealActionId(uuid4()))

    async def test_update_replaces_values_and_keeps_the_deal(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        created = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input()
        )
        clock.advance(60)

        updated = await UpdateDealAction(uow_factory, clock).execute(
            created.id,
            make_deal_action_input(
                action_type=ActionType.PROPOSAL,
                action="제안",
                next_action="견적 회신",
                due_date=date(2026, 3, 1),
                memo="",
            ),
        )

        assert updated.details.deal_id == deal_id
        assert updated.details.action_type is ActionType.PROPOSAL
        assert updated.updated_at == clock.now()
        reloaded = await GetDealAction(uow_factory).execute(created.id)
        assert reloaded.details.action == "제안"
        assert reloaded.details.next_action == "견적 회신"
        assert reloaded.details.due_date == date(2026, 3, 1)
        assert reloaded.created_at == created.created_at

    async def test_delete_action_removes_the_row(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        deal_id: DealId,
    ) -> None:
        created = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input()
        )

        await DeleteDealAction(uow_factory, clock).execute(created.id)

        with pytest.raises(DealActionNotFoundError):
            await GetDealAction(uow_factory).execute(created.id)
        with pytest.raises(DealActionNotFoundError):
            await uow.deal_actions.get(created.id)  # 표시가 아니라 행 삭제
        with pytest.raises(DealActionNotFoundError):
            await DeleteDealAction(uow_factory, clock).execute(created.id)

    async def test_update_requires_the_plan_fields_at_the_input_level(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        created = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input()
        )

        with pytest.raises(InvalidValueError):
            await UpdateDealAction(uow_factory, clock).execute(
                created.id, make_deal_action_input(next_action="  ")
            )
