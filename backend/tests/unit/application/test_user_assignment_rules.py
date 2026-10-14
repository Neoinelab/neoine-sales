"""AC4·6: 담당자·활동자로 새로 지정할 수 있는 것은 재직자뿐. 수정 시 기존 값 유지는 허용 (T17)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidReferenceError
from app.domain.user.value_objects import UserId
from tests.factories import make_customer_input, make_deal_action_input, make_deal_input
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.deal.entities import Deal
    from app.domain.user.entities import User
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

pytestmark = pytest.mark.usefixtures("default_users")


@dataclass
class Env:
    uow: FakeUnitOfWork
    factory: UnitOfWorkFactory
    clock: FixedClock
    customer: Customer
    deal: Deal

    async def resign(self, user: User) -> None:
        async with self.factory() as uow:
            stored = await uow.users.get(user.id)
            stored.resign(self.clock.now())
            await uow.users.update(stored)
            await uow.commit()


@pytest.fixture
async def env(uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock) -> Env:
    customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
    deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
    return Env(uow, uow_factory, clock, customer, deal)


@pytest.fixture
async def resigned(uow_factory: UnitOfWorkFactory) -> User:
    return await seed_user(uow_factory, "gone", Role.SALES, resigned=True)


@pytest.fixture
async def active(uow_factory: UnitOfWorkFactory) -> User:
    return await seed_user(uow_factory, "kim", Role.SALES)


class TestDealOwner:
    async def test_register_with_a_resigned_owner_is_an_invalid_reference(
        self, env: Env, resigned: User
    ) -> None:
        data = make_deal_input(env.customer.id, code="NEW-1", owner_user_id=resigned.id)

        with pytest.raises(InvalidReferenceError) as caught:
            await RegisterDeal(env.factory, env.clock).execute(data)

        assert caught.value.entity == "사용자"
        assert [d.details.code.value for d in await env.uow.deals.list()] == ["DEAL-001"]

    async def test_register_with_an_unknown_owner_is_an_invalid_reference(self, env: Env) -> None:
        data = make_deal_input(env.customer.id, code="NEW-1", owner_user_id=uuid4())

        with pytest.raises(InvalidReferenceError):
            await RegisterDeal(env.factory, env.clock).execute(data)

    async def test_register_with_an_active_owner_takes_the_assignment_lock(
        self, env: Env, active: User
    ) -> None:
        data = make_deal_input(env.customer.id, code="NEW-1", owner_user_id=active.id)

        deal = await RegisterDeal(env.factory, env.clock).execute(data)

        assert deal.details.owner_user_id == active.id
        assert active.id in env.uow.users.assign_locks  # 삭제와의 경쟁을 막는 FOR KEY SHARE 대용

    async def test_update_to_a_resigned_owner_is_rejected_and_changes_nothing(
        self, env: Env, resigned: User
    ) -> None:
        data = make_deal_input(env.customer.id, owner_user_id=resigned.id, name="바뀜")

        with pytest.raises(InvalidReferenceError):
            await UpdateDeal(env.factory, env.clock).execute(env.deal.id, data)

        stored = await env.uow.deals.get(env.deal.id)
        assert stored.details.owner_user_id == env.deal.details.owner_user_id
        assert stored.details.name == env.deal.details.name

    async def test_update_keeping_an_already_resigned_owner_is_allowed(
        self, env: Env, active: User
    ) -> None:
        owned = await RegisterDeal(env.factory, env.clock).execute(
            make_deal_input(env.customer.id, code="OLD-1", owner_user_id=active.id)
        )
        await env.resign(active)
        data = make_deal_input(
            env.customer.id, code="OLD-1", owner_user_id=active.id, name="다른 필드만"
        )

        updated = await UpdateDeal(env.factory, env.clock).execute(owned.id, data)

        assert updated.details.owner_user_id == active.id
        assert (await env.uow.deals.get(owned.id)).details.name == "다른 필드만"

    async def test_update_from_a_resigned_owner_to_an_active_one_is_allowed(
        self, env: Env, active: User, uow_factory: UnitOfWorkFactory
    ) -> None:
        leaver = await seed_user(uow_factory, "leaver", Role.SALES)
        owned = await RegisterDeal(env.factory, env.clock).execute(
            make_deal_input(env.customer.id, code="OLD-2", owner_user_id=leaver.id)
        )
        await env.resign(leaver)
        data = make_deal_input(env.customer.id, code="OLD-2", owner_user_id=active.id)

        updated = await UpdateDeal(env.factory, env.clock).execute(owned.id, data)

        assert updated.details.owner_user_id == active.id


class TestActionActor:
    async def test_register_with_a_resigned_actor_is_an_invalid_reference(
        self, env: Env, resigned: User
    ) -> None:
        data = make_deal_action_input(actor_user_id=resigned.id)

        with pytest.raises(InvalidReferenceError) as caught:
            await RegisterDealAction(env.factory, env.clock).execute(env.deal.id, data)

        assert caught.value.entity == "사용자"
        assert not await env.uow.deal_actions.exists_for_deal(env.deal.id)

    async def test_register_with_an_unknown_actor_is_an_invalid_reference(self, env: Env) -> None:
        data = make_deal_action_input(actor_user_id=UserId(uuid4()))

        with pytest.raises(InvalidReferenceError):
            await RegisterDealAction(env.factory, env.clock).execute(env.deal.id, data)

    async def test_register_with_an_active_actor_takes_the_assignment_lock(
        self, env: Env, active: User
    ) -> None:
        data = make_deal_action_input(actor_user_id=active.id)

        action = await RegisterDealAction(env.factory, env.clock).execute(env.deal.id, data)

        assert action.details.actor_user_id == active.id
        assert active.id in env.uow.users.assign_locks

    async def test_update_to_a_resigned_actor_is_rejected(self, env: Env, resigned: User) -> None:
        register = RegisterDealAction(env.factory, env.clock)
        action = await register.execute(env.deal.id, make_deal_action_input())
        data = make_deal_action_input(actor_user_id=resigned.id, memo="바뀜")

        with pytest.raises(InvalidReferenceError):
            await UpdateDealAction(env.factory, env.clock).execute(action.id, data)

        stored = await env.uow.deal_actions.get(action.id)
        assert stored.details.actor_user_id == action.details.actor_user_id
        assert stored.details.memo == action.details.memo

    async def test_update_keeping_an_already_resigned_actor_is_allowed(
        self, env: Env, active: User
    ) -> None:
        register = RegisterDealAction(env.factory, env.clock)
        action = await register.execute(
            env.deal.id, make_deal_action_input(actor_user_id=active.id)
        )
        await env.resign(active)
        data = make_deal_action_input(actor_user_id=active.id, memo="메모만 수정")

        updated = await UpdateDealAction(env.factory, env.clock).execute(action.id, data)

        assert updated.details.actor_user_id == active.id
        assert (await env.uow.deal_actions.get(action.id)).details.memo == "메모만 수정"
