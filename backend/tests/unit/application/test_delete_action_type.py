"""DeleteActionType(AC-6): 쓰는 Action이 없을 때만 삭제(기본 유형 포함), 사용 중이면 거부."""

from typing import TYPE_CHECKING

import pytest

from app.application.action_type.delete_action_type import DeleteActionType
from app.domain.action_type.errors import ActionTypeInUseError, ActionTypeNotFoundError
from app.domain.action_type.values import ActionTypeId
from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES, type_id
from tests.fakes.catalog_seed import seed_action_types
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import KIM

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork
    from tests.unit.application.action_env import ActionEnv

MEETING = ActionTypeId(type_id("미팅"))
DEMO = ActionTypeId(type_id("데모"))


@pytest.fixture
def seeded(seeded: FakeUnitOfWork) -> FakeUnitOfWork:
    """기본 코드·Label에 더해 마이그레이션이 넣는 기본 Action 유형 8개가 있는 UoW."""
    seed_action_types(seeded)
    return seeded


async def test_delete_an_unused_default_type_removes_only_that_type(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    await DeleteActionType(uow_factory).execute(DEMO)

    names = [t.name for t in await seeded.action_types.list()]
    assert names == [n for n in DEFAULT_ACTION_TYPE_NAMES if n != "데모"]
    assert seeded.commits == 1


async def test_delete_a_used_type_is_refused_with_the_action_count_and_keeps_the_row(
    action_env: ActionEnv,
) -> None:
    for _ in range(3):
        await action_env.act(KIM, action_type="미팅")

    with raises_with(ActionTypeInUseError, "사용 중인 유형은 삭제할 수 없습니다. (Action 3건)"):
        await DeleteActionType(action_env.env.uow_factory).execute(MEETING)

    assert (await action_env.env.uow.action_types.get(MEETING)).name == "미팅"


async def test_delete_ignores_the_usage_of_other_types(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action_type="미팅")

    await DeleteActionType(action_env.env.uow_factory).execute(DEMO)

    with pytest.raises(ActionTypeNotFoundError):
        await action_env.env.uow.action_types.get(DEMO)


async def test_a_type_becomes_deletable_after_its_actions_are_deleted(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM, action_type="미팅")
    await action_env.delete.execute(action.id, KIM)

    await DeleteActionType(action_env.env.uow_factory).execute(MEETING)

    with pytest.raises(ActionTypeNotFoundError):
        await action_env.env.uow.action_types.get(MEETING)


async def test_delete_a_missing_type_is_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(ActionTypeNotFoundError):
        await DeleteActionType(uow_factory).execute(ActionTypeId(new_id()))
