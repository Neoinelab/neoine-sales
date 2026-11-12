"""RegisterActionType: 생성자 기록, 이름 정규화, 대소문자 무시 중복 거부."""

from typing import TYPE_CHECKING

import pytest

from app.application.action_type.register_action_type import RegisterActionType
from app.domain.action_type.errors import DuplicateActionTypeNameError
from app.domain.common.errors import InvalidValueError
from tests.factories_auth import make_user
from tests.fakes.catalog_seed import seed_action_types
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserId
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
def seeded(seeded: FakeUnitOfWork) -> FakeUnitOfWork:
    """기본 코드·Label에 더해 마이그레이션이 넣는 기본 Action 유형 8개가 있는 UoW."""
    seed_action_types(seeded)
    return seeded


async def _creator(uow: FakeUnitOfWork) -> UserId:
    user = make_user("kim")
    await uow.users.add(user)
    return user.id


async def _names(uow: FakeUnitOfWork) -> list[str]:
    return [t.name for t in await uow.action_types.list()]


async def test_register_records_the_creator_and_is_not_default(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """등록한 유형은 직접 만든 항목이고 만든 사람·서버 시각이 기록되며 사용 수는 0이다.

    테스트 코드: CL-028
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when: '웨비나'를 등록한다
    result = await RegisterActionType(uow_factory, clock).execute("웨비나", creator)

    # then: 저장된 유형은 기본이 아니고 만든 사람·시각이 기록되며 사용 수 0이다
    stored = await seeded.action_types.get(result.action_type.id)
    assert stored.name == "웨비나"
    assert stored.is_default is False
    assert stored.default_order is None
    assert stored.created_by_user_id == creator
    assert stored.created_at == stored.updated_at == clock.now()
    assert result.usage_count == 0


async def test_register_commits_the_new_type(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """등록은 한 번 커밋하고 새 트랜잭션에서도 새 유형이 보인다.

    테스트 코드: CL-028
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when: '웨비나'를 등록한다
    await RegisterActionType(uow_factory, clock).execute("웨비나", creator)

    # then: 커밋 1회이고 새 트랜잭션의 목록에 있다
    assert seeded.commits == 1
    async with uow_factory() as fresh:  # 새 트랜잭션에서도 보인다(커밋됨)
        assert "웨비나" in [t.name for t in await fresh.action_types.list()]


async def test_register_trims_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """유형 이름은 앞뒤 공백을 지운 뒤 저장한다.

    테스트 코드: CL-028
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when: '  웨비나  '를 등록한다
    result = await RegisterActionType(uow_factory, clock).execute("  웨비나  ", creator)

    # then: 이름은 '웨비나'다
    assert result.action_type.name == "웨비나"


@pytest.mark.parametrize("name", ["demo", "DEMO", " Demo "])
async def test_register_a_name_equal_to_an_existing_one_ignoring_case_conflicts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """이미 있는 유형과 대소문자·공백만 다른 이름은 중복으로 거절하고 저장하지 않는다.

    테스트 코드: CL-030
    """
    # given: 'Demo' 유형이 있다
    creator = await _creator(seeded)
    await RegisterActionType(uow_factory, clock).execute("Demo", creator)
    before = await _names(seeded)

    # when: 'demo', 'DEMO', ' Demo '로 등록한다
    with raises_with(DuplicateActionTypeNameError, "이미 있는 유형 이름입니다."):
        await RegisterActionType(uow_factory, clock).execute(name, creator)

    # then: 중복 문구 오류이고 유형 목록은 그대로다
    assert await _names(seeded) == before


async def test_register_a_seeded_default_name_conflicts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """기본 유형 이름과 같은 이름은 중복으로 거절한다.

    테스트 코드: CL-030
    """
    # given: 기본 유형 '미팅'이 있다
    creator = await _creator(seeded)

    # when·then: '미팅'을 등록한다 → 중복 오류다
    with pytest.raises(DuplicateActionTypeNameError):
        await RegisterActionType(uow_factory, clock).execute("미팅", creator)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "유형을 입력하세요."),
        ("   ", "유형을 입력하세요."),
        ("가" * 51, "유형은 50자 이내로 입력하세요."),
    ],
    ids=["empty", "blank", "51-chars"],
)
async def test_register_an_invalid_name_stores_nothing(
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    name: str,
    message: str,
) -> None:
    """빈 이름·공백뿐인 이름·51자 이름은 문구에 맞는 오류로 거절하고 저장하지 않는다.

    테스트 코드: CL-031
    """
    # given: 기본 유형 8개가 있다
    creator = await _creator(seeded)
    before = await _names(seeded)

    # when: 유효하지 않은 이름으로 등록한다
    with raises_with(InvalidValueError, message):
        await RegisterActionType(uow_factory, clock).execute(name, creator)

    # then: 필수·길이 문구 오류이고 목록·커밋은 그대로다
    assert await _names(seeded) == before
    assert seeded.commits == 0


async def test_register_accepts_a_50_code_point_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """유형 이름은 이모지 50개(50 코드 포인트)까지 저장된다.

    테스트 코드: CL-031
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when: 이모지 50개 이름을 등록한다
    result = await RegisterActionType(uow_factory, clock).execute("😀" * 50, creator)

    # then: 이름이 그대로 저장된다
    assert result.action_type.name == "😀" * 50


async def test_register_rejects_nul(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """NUL 문자가 든 유형 이름은 등록할 수 없다.

    테스트 코드: CL-032
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when·then: NUL이 든 이름을 등록한다 → NUL 오류다
    with pytest.raises(InvalidValueError, match="NUL"):
        await RegisterActionType(uow_factory, clock).execute("데\x00모", creator)
