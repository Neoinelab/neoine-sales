"""RegisterActionType(AC-2·3·4): 생성자 기록, 이름 정규화, 대소문자 무시 중복 거부."""

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
    creator = await _creator(seeded)

    result = await RegisterActionType(uow_factory, clock).execute("웨비나", creator)

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
    creator = await _creator(seeded)

    await RegisterActionType(uow_factory, clock).execute("웨비나", creator)

    assert seeded.commits == 1
    async with uow_factory() as fresh:  # 새 트랜잭션에서도 보인다(커밋됨)
        assert "웨비나" in [t.name for t in await fresh.action_types.list()]


async def test_register_trims_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

    result = await RegisterActionType(uow_factory, clock).execute("  웨비나  ", creator)

    assert result.action_type.name == "웨비나"


@pytest.mark.parametrize("name", ["demo", "DEMO", " Demo "])
async def test_register_a_name_equal_to_an_existing_one_ignoring_case_conflicts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    creator = await _creator(seeded)
    await RegisterActionType(uow_factory, clock).execute("Demo", creator)
    before = await _names(seeded)

    with raises_with(DuplicateActionTypeNameError, "이미 있는 유형 이름입니다."):
        await RegisterActionType(uow_factory, clock).execute(name, creator)

    assert await _names(seeded) == before


async def test_register_a_seeded_default_name_conflicts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

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
    creator = await _creator(seeded)
    before = await _names(seeded)

    with raises_with(InvalidValueError, message):
        await RegisterActionType(uow_factory, clock).execute(name, creator)

    assert await _names(seeded) == before
    assert seeded.commits == 0


async def test_register_accepts_a_50_code_point_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

    result = await RegisterActionType(uow_factory, clock).execute("😀" * 50, creator)

    assert result.action_type.name == "😀" * 50


async def test_register_rejects_nul(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

    with pytest.raises(InvalidValueError, match="NUL"):
        await RegisterActionType(uow_factory, clock).execute("데\x00모", creator)
