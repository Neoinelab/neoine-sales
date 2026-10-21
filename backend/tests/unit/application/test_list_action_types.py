"""ListActionTypes(AC-1): 기본 유형 먼저, 직접 만든 유형은 소문자 이름순, 사용 수 포함."""

from typing import TYPE_CHECKING

import pytest

from app.application.action_type.list_action_types import ListActionTypes
from app.application.action_type.register_action_type import RegisterActionType
from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES
from tests.factories_auth import make_user
from tests.fakes.catalog_seed import seed_action_types
from tests.unit.application.action_env import KIM

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
    from tests.unit.application.action_env import ActionEnv


@pytest.fixture
def seeded(seeded: FakeUnitOfWork) -> FakeUnitOfWork:
    """기본 코드·Label에 더해 마이그레이션이 넣는 기본 Action 유형 8개가 있는 UoW."""
    seed_action_types(seeded)
    return seeded


async def test_list_returns_the_eight_defaults_in_seed_order_without_creators(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    result = await ListActionTypes(uow_factory).execute()

    assert [u.action_type.name for u in result] == list(DEFAULT_ACTION_TYPE_NAMES)
    assert all(u.action_type.is_default for u in result)
    assert all(u.action_type.created_by_user_id is None for u in result)
    assert [u.usage_count for u in result] == [0] * 8


async def test_list_puts_custom_types_after_defaults_sorted_by_lower_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = make_user("creator")
    await seeded.users.add(creator)
    register = RegisterActionType(uow_factory, clock)
    for name in ("나중에", "가장 먼저", "Zeta", "alpha"):
        await register.execute(name, creator.id)

    result = await ListActionTypes(uow_factory).execute()

    names = [u.action_type.name for u in result]
    assert names == [*DEFAULT_ACTION_TYPE_NAMES, "alpha", "Zeta", "가장 먼저", "나중에"]


async def test_list_reports_how_many_actions_use_each_type(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action_type="미팅")
    await action_env.act(KIM, action_type="미팅")
    await action_env.act(KIM, action_type="데모")

    usage = {
        u.action_type.name: u.usage_count
        for u in await ListActionTypes(action_env.env.uow_factory).execute()
    }

    assert usage["미팅"] == 2
    assert usage["데모"] == 1
    assert usage["통화"] == 0
