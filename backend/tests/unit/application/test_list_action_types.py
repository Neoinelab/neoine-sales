"""ListActionTypes: 기본 유형 먼저, 직접 만든 유형은 소문자 이름순, 사용 수 포함."""

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
    """기본 Action 유형 8개가 시드 순서로 나오고 만든 사람이 없으며 사용 수는 0이다.

    테스트 코드: CL-025
    """
    # when: 유형 목록을 읽는다
    result = await ListActionTypes(uow_factory).execute()

    # then: 8개가 시드 순서·기본 표시·만든 사람 없음·사용 0이다
    assert [u.action_type.name for u in result] == list(DEFAULT_ACTION_TYPE_NAMES)
    assert all(u.action_type.is_default for u in result)
    assert all(u.action_type.created_by_user_id is None for u in result)
    assert [u.usage_count for u in result] == [0] * 8


async def test_list_puts_custom_types_after_defaults_sorted_by_lower_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """직접 만든 유형은 기본 유형 뒤에 소문자 이름 코드 포인트 순으로 나온다.

    테스트 코드: CL-026
    """
    # given: '나중에', '가장 먼저', 'Zeta', 'alpha'를 차례로 만들었다
    creator = make_user("creator")
    await seeded.users.add(creator)
    register = RegisterActionType(uow_factory, clock)
    for name in ("나중에", "가장 먼저", "Zeta", "alpha"):
        await register.execute(name, creator.id)

    # when: 유형 목록을 읽는다
    result = await ListActionTypes(uow_factory).execute()

    # then: 기본 8개 뒤에 alpha, Zeta, 가장 먼저, 나중에 순이다
    names = [u.action_type.name for u in result]
    assert names == [*DEFAULT_ACTION_TYPE_NAMES, "alpha", "Zeta", "가장 먼저", "나중에"]


async def test_list_reports_how_many_actions_use_each_type(action_env: ActionEnv) -> None:
    """유형의 사용 수는 그 유형을 쓰는 Action 수다.

    테스트 코드: CL-027
    """
    # given: '미팅' Action 2건과 '데모' Action 1건이 있다
    await action_env.act(KIM, action_type="미팅")
    await action_env.act(KIM, action_type="미팅")
    await action_env.act(KIM, action_type="데모")

    # when: 유형 목록을 읽는다
    usage = {
        u.action_type.name: u.usage_count
        for u in await ListActionTypes(action_env.env.uow_factory).execute()
    }

    # then: '미팅' 2, '데모' 1, '통화' 0이다
    assert usage["미팅"] == 2
    assert usage["데모"] == 1
    assert usage["통화"] == 0
