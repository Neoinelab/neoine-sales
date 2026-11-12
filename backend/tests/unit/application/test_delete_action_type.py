"""DeleteActionType: 쓰는 Action이 없을 때만 삭제(기본 유형 포함), 사용 중이면 거부."""

from typing import TYPE_CHECKING

import pytest

from app.application.action_type.delete_action_type import DeleteActionType
from app.application.action_type.register_action_type import RegisterActionType
from app.domain.action_type.errors import ActionTypeInUseError, ActionTypeNotFoundError
from app.domain.action_type.values import ActionTypeId
from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES, type_id
from tests.factories_auth import make_user
from tests.fakes.catalog_seed import seed_action_types
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import KIM

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
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
    """쓰이지 않는 유형은 기본 유형이어도 삭제되고 그 유형만 사라진다.

    테스트 코드: CL-040
    """
    # when: '데모'를 삭제한다
    await DeleteActionType(uow_factory).execute(DEMO)

    # then: 목록에서 '데모'만 빠지고 커밋은 1회다
    names = [t.name for t in await seeded.action_types.list()]
    assert names == [n for n in DEFAULT_ACTION_TYPE_NAMES if n != "데모"]
    assert seeded.commits == 1


async def test_delete_a_used_type_is_refused_with_the_action_count_and_keeps_the_row(
    action_env: ActionEnv,
) -> None:
    """Action이 쓰는 유형을 지우면 실제 Action 수가 든 오류이고 유형은 남는다.

    테스트 코드: CL-041
    """
    # given: '미팅' Action 3건이 있다
    for _ in range(3):
        await action_env.act(KIM, action_type="미팅")

    # when: '미팅'을 삭제한다
    with raises_with(ActionTypeInUseError, "사용 중인 유형은 삭제할 수 없습니다. (Action 3건)"):
        await DeleteActionType(action_env.env.uow_factory).execute(MEETING)

    # then: '(Action 3건)' 오류이고 유형은 그대로다
    assert (await action_env.env.uow.action_types.get(MEETING)).name == "미팅"


async def test_delete_ignores_the_usage_of_other_types(action_env: ActionEnv) -> None:
    """다른 유형의 사용은 삭제 판정에 영향을 주지 않는다.

    테스트 코드: CL-040
    """
    # given: '미팅'만 Action이 쓴다
    await action_env.act(KIM, action_type="미팅")

    # when: '데모'를 삭제한다
    await DeleteActionType(action_env.env.uow_factory).execute(DEMO)

    # then: '데모'는 사라진다
    with pytest.raises(ActionTypeNotFoundError):
        await action_env.env.uow.action_types.get(DEMO)


async def test_a_type_becomes_deletable_after_its_actions_are_deleted(
    action_env: ActionEnv,
) -> None:
    """유형을 쓰던 Action이 모두 지워지면 유형을 삭제할 수 있다.

    테스트 코드: CL-042
    """
    # given: '미팅' Action 1건이 있었고 그 Action을 삭제했다
    action = await action_env.act(KIM, action_type="미팅")
    await action_env.delete.execute(action.id, KIM)

    # when: '미팅'을 삭제한다
    await DeleteActionType(action_env.env.uow_factory).execute(MEETING)

    # then: 유형이 사라진다
    with pytest.raises(ActionTypeNotFoundError):
        await action_env.env.uow.action_types.get(MEETING)


async def test_delete_a_missing_type_is_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """없는 유형을 삭제하면 찾을 수 없음 오류다.

    테스트 코드: CL-038
    """
    # when·then: 없는 id를 삭제한다 → 유형을 찾을 수 없음 오류다
    with pytest.raises(ActionTypeNotFoundError):
        await DeleteActionType(uow_factory).execute(ActionTypeId(new_id()))


async def test_the_name_of_a_deleted_type_can_be_registered_again(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """지운 유형의 이름은 다시 등록할 수 있다.

    테스트 코드: CL-043
    """
    # given: 기본 유형 '데모'를 삭제했다
    creator = make_user("kim")
    await seeded.users.add(creator)
    await DeleteActionType(uow_factory).execute(DEMO)

    # when: '데모'를 다시 등록한다
    result = await RegisterActionType(uow_factory, clock).execute("데모", creator.id)

    # then: 직접 만든 유형으로 등록되고 이름은 하나뿐이다
    assert result.action_type.name == "데모"
    assert result.action_type.is_default is False
    assert [t.name for t in await seeded.action_types.list()].count("데모") == 1
