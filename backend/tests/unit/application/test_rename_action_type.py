"""RenameActionType: 이름 변경(기본 유형 포함), 대소문자만 바꾸기 허용, 사용 수 응답."""

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
    """기본 유형 이름을 바꿔도 기본 표시·자리가 유지되고 수정 시각이 갱신된다.

    테스트 코드: CL-034
    """
    # given: 기본 유형 '미팅'(2번째)이 있고 시간이 흘렀다
    clock.advance(60)

    # when: '  회의  '로 이름을 바꾼다
    result = await RenameActionType(uow_factory, clock).execute(MEETING, "  회의  ")

    # then: 이름만 바뀌고 기본 표시·순서는 같으며 updated_at이 서버 시각이다
    stored = await seeded.action_types.get(MEETING)
    assert result.action_type.name == stored.name == "회의"
    assert (stored.is_default, stored.default_order) == (True, 2)
    assert stored.updated_at == clock.now()


async def test_rename_commits_once(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """이름 변경은 한 번 커밋한다.

    테스트 코드: CL-034
    """
    # when: 이름을 바꾼다
    await RenameActionType(uow_factory, clock).execute(MEETING, "회의")

    # then: 커밋은 1회다
    assert seeded.commits == 1


async def test_rename_only_the_case_of_its_own_name_is_allowed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """유형 자기 이름의 대소문자만 바꾸는 것은 허용된다.

    테스트 코드: CL-035
    """
    # given: 'Meeting'으로 바꾼 유형이 있다
    first = await RenameActionType(uow_factory, clock).execute(MEETING, "Meeting")

    # when: 'MEETING'으로 바꾼다
    second = await RenameActionType(uow_factory, clock).execute(first.action_type.id, "MEETING")

    # then: 이름이 'MEETING'이다
    assert second.action_type.name == "MEETING"


async def test_rename_to_another_types_name_ignoring_case_conflicts_and_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """다른 유형의 이름(대소문자 무시)으로 바꾸면 중복으로 거절하고 이름은 그대로다.

    테스트 코드: CL-036
    """
    # given: '데모' 유형을 'Demo'로 바꿔 두었다
    other = await RenameActionType(uow_factory, clock).execute(
        ActionTypeId(type_id("데모")), "Demo"
    )
    assert other.action_type.name == "Demo"

    # when: '미팅'을 'demo'로 바꾼다
    with raises_with(DuplicateActionTypeNameError, "이미 있는 유형 이름입니다."):
        await RenameActionType(uow_factory, clock).execute(MEETING, "demo")

    # then: 중복 문구 오류이고 '미팅'은 그대로다
    assert (await seeded.action_types.get(MEETING)).name == "미팅"


async def test_rename_a_missing_type_is_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """없는 유형의 이름을 바꾸면 찾을 수 없음 오류다.

    테스트 코드: CL-038
    """
    # when·then: 없는 id의 이름을 바꾼다 → 유형을 찾을 수 없음 오류다
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
    """공백뿐이거나 51자인 새 유형 이름은 거절하고 이름은 그대로다.

    테스트 코드: CL-037
    """
    # when: 유효하지 않은 이름으로 바꾼다
    with raises_with(InvalidValueError, message):
        await RenameActionType(uow_factory, clock).execute(MEETING, name)

    # then: 필수·길이 문구 오류이고 이름·커밋은 그대로다
    assert (await seeded.action_types.get(MEETING)).name == "미팅"
    assert seeded.commits == 0


async def test_rename_reports_the_usage_count_of_the_type(action_env: ActionEnv) -> None:
    """이름 변경 결과에 그 유형을 쓰는 Action 수가 실린다.

    테스트 코드: CL-034
    """
    # given: '미팅' Action 2건이 있다
    await action_env.act(KIM, action_type="미팅")
    await action_env.act(KIM, action_type="미팅")
    clock = action_env.env.clock

    # when: '미팅'을 '회의'로 바꾼다
    result = await RenameActionType(action_env.env.uow_factory, clock).execute(MEETING, "회의")

    # then: 사용 수는 2다
    assert result.usage_count == 2


async def test_a_rename_is_visible_on_the_actions_that_use_the_type(action_env: ActionEnv) -> None:
    """유형 이름을 바꾸면 그 유형을 쓰는 Action은 새 이름을 보인다.

    테스트 코드: CL-039
    """
    # given: '미팅' 유형으로 등록한 Action이 있다
    action = await action_env.act(KIM, action_type="미팅")

    # when: '미팅'을 '회의'로 바꾼다
    await RenameActionType(action_env.env.uow_factory, action_env.env.clock).execute(
        MEETING, "회의"
    )

    # then: Action의 유형은 같은 id에 이름 '회의'다
    assert (await action_env.stored(action.id)).content.action_type.name == "회의"


async def test_a_rename_does_not_rewrite_the_history_that_is_already_written(
    action_env: ActionEnv,
) -> None:
    """이름을 바꿔도 이미 남은 History 문구는 다시 쓰지 않는다.

    테스트 코드: CL-039
    """
    # given: '미팅' 유형으로 등록한 Action과 그 등록 History가 있다
    await action_env.act(KIM, action_type="미팅")
    rows_before = await action_env.rows()

    # when: '미팅'을 '회의'로 바꾼다
    await RenameActionType(action_env.env.uow_factory, action_env.env.clock).execute(
        MEETING, "회의"
    )

    # then: History 행은 그대로이고 '미팅 ·' 문구를 담고 있다
    assert await action_env.rows() == rows_before
    assert "미팅 ·" in rows_before[0][3]
