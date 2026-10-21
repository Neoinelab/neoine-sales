"""RenameActionType(AC-4·5): 이름 변경(기본 유형 포함), 대소문자만 바꾸기 허용, 사용 수 응답."""

from typing import TYPE_CHECKING

import pytest

from app.application.action_type.rename_action_type import RenameActionType
from app.domain.action_type.errors import ActionTypeNotFoundError, DuplicateActionTypeNameError
from app.domain.action_type.values import ActionTypeId
from app.domain.common.errors import InvalidValueError
from tests.factories_action_type import type_id
from tests.fakes.catalog_seed import seed_action_types
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import KIM

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
    from tests.unit.application.action_env import ActionEnv

MEETING = ActionTypeId(type_id("미팅"))


@pytest.fixture
def seeded(seeded: FakeUnitOfWork) -> FakeUnitOfWork:
    """기본 코드·Label에 더해 마이그레이션이 넣는 기본 Action 유형 8개가 있는 UoW."""
    seed_action_types(seeded)
    return seeded


async def test_rename_a_default_type_keeps_its_default_flag_and_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    clock.advance(60)

    result = await RenameActionType(uow_factory, clock).execute(MEETING, "  회의  ")

    stored = await seeded.action_types.get(MEETING)
    assert result.action_type.name == stored.name == "회의"
    assert (stored.is_default, stored.default_order) == (True, 2)
    assert stored.updated_at == clock.now()


async def test_rename_commits_once(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    await RenameActionType(uow_factory, clock).execute(MEETING, "회의")

    assert seeded.commits == 1


async def test_rename_only_the_case_of_its_own_name_is_allowed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    first = await RenameActionType(uow_factory, clock).execute(MEETING, "Meeting")

    second = await RenameActionType(uow_factory, clock).execute(first.action_type.id, "MEETING")

    assert second.action_type.name == "MEETING"


async def test_rename_to_another_types_name_ignoring_case_conflicts_and_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    other = await RenameActionType(uow_factory, clock).execute(
        ActionTypeId(type_id("데모")), "Demo"
    )
    assert other.action_type.name == "Demo"

    with raises_with(DuplicateActionTypeNameError, "이미 있는 유형 이름입니다."):
        await RenameActionType(uow_factory, clock).execute(MEETING, "demo")

    assert (await seeded.action_types.get(MEETING)).name == "미팅"


async def test_rename_a_missing_type_is_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(ActionTypeNotFoundError):
        await RenameActionType(uow_factory, clock).execute(ActionTypeId(new_id()), "회의")


@pytest.mark.parametrize(
    ("name", "message"),
    [("   ", "유형을 입력하세요."), ("가" * 51, "유형은 50자 이내로 입력하세요.")],
    ids=["blank", "51-chars"],
)
async def test_rename_to_an_invalid_name_keeps_the_name(
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    name: str,
    message: str,
) -> None:
    with raises_with(InvalidValueError, message):
        await RenameActionType(uow_factory, clock).execute(MEETING, name)

    assert (await seeded.action_types.get(MEETING)).name == "미팅"
    assert seeded.commits == 0


async def test_rename_reports_the_usage_count_of_the_type(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action_type="미팅")
    await action_env.act(KIM, action_type="미팅")
    clock = action_env.env.clock

    result = await RenameActionType(action_env.env.uow_factory, clock).execute(MEETING, "회의")

    assert result.usage_count == 2


async def test_a_rename_is_visible_on_the_actions_that_use_the_type(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, action_type="미팅")

    await RenameActionType(action_env.env.uow_factory, action_env.env.clock).execute(
        MEETING, "회의"
    )

    assert (await action_env.stored(action.id)).content.action_type.name == "회의"


async def test_a_rename_does_not_rewrite_the_history_that_is_already_written(
    action_env: ActionEnv,
) -> None:
    await action_env.act(KIM, action_type="미팅")
    rows_before = await action_env.rows()

    await RenameActionType(action_env.env.uow_factory, action_env.env.clock).execute(
        MEETING, "회의"
    )

    assert await action_env.rows() == rows_before
    assert "미팅 ·" in rows_before[0][3]
