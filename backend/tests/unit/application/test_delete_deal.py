"""DeleteDeal: 물리 삭제. 활동 또는 단계 변경 이력이 있으면 DealInUseError(FK 기준과 같다)."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.change_stage import ChangeDealStage
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_deal import GetDeal
from app.application.deal.register_deal import RegisterDeal
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
from app.domain.common.errors import InvalidStateError
from app.domain.deal.errors import DealInUseError, DealNotFoundError
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import DealId
from tests.factories import (
    make_customer_input,
    make_deal_action_input,
    make_deal_input,
    make_stage_change_input,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
async def deal(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> Deal:
    customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
    return await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))


async def test_delete_deal_without_actions_removes_it_physically(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    await DeleteDeal(uow_factory, clock).execute(deal.id)

    with pytest.raises(DealNotFoundError):
        await GetDeal(uow_factory).execute(deal.id)
    with pytest.raises(DealNotFoundError):
        await uow.deals.get(deal.id, include_deleted=True)


async def test_deleted_deal_code_can_be_reused(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    await DeleteDeal(uow_factory, clock).execute(deal.id)

    again = await RegisterDeal(uow_factory, clock).execute(
        make_deal_input(deal.details.customer_id)
    )

    assert again.details.code == deal.details.code
    assert again.id != deal.id


async def test_delete_deal_with_actions_raises_deal_in_use(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    action = await RegisterDealAction(uow_factory, clock).execute(deal.id, make_deal_action_input())

    with pytest.raises(DealInUseError) as raised:
        await DeleteDeal(uow_factory, clock).execute(deal.id)

    assert "활동 또는 단계 변경 이력" in str(raised.value)
    assert not (await uow.deals.get(deal.id)).is_deleted
    assert (await uow.deal_actions.get(action.id)).id == action.id


async def test_delete_deal_with_only_stage_changes_raises_deal_in_use(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    await ChangeDealStage(uow_factory, clock).execute(
        deal.id, make_stage_change_input(stage=DealStage.INTRODUCTION)
    )
    assert await uow.deal_actions.exists_for_deal(deal.id) is False

    with pytest.raises(DealInUseError):
        await DeleteDeal(uow_factory, clock).execute(deal.id)

    assert (await uow.deals.get(deal.id)).stage is DealStage.INTRODUCTION
    history = await uow.deal_stage_changes.search(DealStageChangeQuery(deal_id=deal.id))
    assert len(history) == 1


async def test_deal_in_use_error_is_an_invalid_state_for_callers(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    await RegisterDealAction(uow_factory, clock).execute(deal.id, make_deal_action_input())

    with pytest.raises(InvalidStateError):
        await DeleteDeal(uow_factory, clock).execute(deal.id)


async def test_delete_deal_succeeds_after_all_actions_are_deleted(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    register = RegisterDealAction(uow_factory, clock)
    first = await register.execute(deal.id, make_deal_action_input())
    second = await register.execute(deal.id, make_deal_action_input(action="후속"))
    delete_action = DeleteDealAction(uow_factory, clock)
    await delete_action.execute(first.id)
    with pytest.raises(DealInUseError):
        await DeleteDeal(uow_factory, clock).execute(deal.id)
    await delete_action.execute(second.id)

    await DeleteDeal(uow_factory, clock).execute(deal.id)

    with pytest.raises(DealNotFoundError):
        await uow.deals.get(deal.id, include_deleted=True)


async def test_unknown_deal_delete_raises_not_found(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(DealNotFoundError):
        await DeleteDeal(uow_factory, clock).execute(DealId(uuid4()))


async def test_deleting_an_already_deleted_deal_raises_not_found(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    await DeleteDeal(uow_factory, clock).execute(deal.id)

    with pytest.raises(DealNotFoundError):
        await DeleteDeal(uow_factory, clock).execute(deal.id)


async def test_guard_rejection_commits_nothing(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal: Deal
) -> None:
    await RegisterDealAction(uow_factory, clock).execute(deal.id, make_deal_action_input())
    commits = uow.commits

    with pytest.raises(DealInUseError):
        await DeleteDeal(uow_factory, clock).execute(deal.id)

    assert uow.commits == commits
