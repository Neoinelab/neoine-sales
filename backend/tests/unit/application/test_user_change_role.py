"""R1 ChangeUserRole(AC1-1~1-8): 역할 변경, 세션 유지·다음 요청부터 새 역할, 보호 규칙."""

from typing import TYPE_CHECKING

import pytest
from app.application.user.change_user_role import ChangeUserRole

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId
from tests.fakes.admin_stack import DEV_ACTOR
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FixedClock

SELF_CHANGE = "자기 자신의 역할은 바꿀 수 없습니다."
LAST_ADMIN = "마지막 관리자의 역할은 바꿀 수 없습니다."
RESIGNED = "이미 퇴사 처리된 사용자입니다"
DEV_ONLY = "개발 로그인 전용 사용자의 역할은 바꿀 수 없습니다."


@pytest.fixture
def change_role(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> ChangeUserRole:
    return ChangeUserRole(uow_factory, clock)


async def _role_of(uow_factory: UnitOfWorkFactory, user_id: UserId) -> Role:
    async with uow_factory() as uow:
        return (await uow.users.get(user_id)).role


async def test_change_user_role_saves_new_role(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    changed = await change_role.execute(
        user_id=target.id, role=Role.USER, actor=root.to_principal()
    )

    assert changed.role is Role.USER
    assert await _role_of(uow_factory, target.id) is Role.USER


async def test_change_user_role_touches_updated_at_with_the_clock(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    clock.advance(600)

    changed = await change_role.execute(
        user_id=target.id, role=Role.ADMIN, actor=root.to_principal()
    )

    assert changed.updated_at == clock.now()
    async with uow_factory() as uow:
        assert (await uow.users.get(target.id)).updated_at == clock.now()


async def test_change_user_role_keeps_sessions_of_the_target(
    change_role: ChangeUserRole, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    first = (await auth.issue.execute(target.to_principal())).token
    second = (await auth.issue.execute(target.to_principal())).token

    await change_role.execute(user_id=target.id, role=Role.USER, actor=root.to_principal())

    assert await session_is_active(uow_factory, first)
    assert await session_is_active(uow_factory, second)


async def test_authenticate_returns_new_role_after_change(
    change_role: ChangeUserRole, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(target.to_principal())).token
    assert (await auth.authenticate.execute(token)).role is Role.SALES

    await change_role.execute(user_id=target.id, role=Role.USER, actor=root.to_principal())

    assert (await auth.authenticate.execute(token)).role is Role.USER


async def test_change_user_role_refuses_oneself(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with raises_with(InvalidStateError, SELF_CHANGE):
        await change_role.execute(user_id=root.id, role=Role.USER, actor=root.to_principal())

    assert await _role_of(uow_factory, root.id) is Role.ADMIN


async def test_change_user_role_refuses_demoting_the_last_admin(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await seed_user(uow_factory, "kim", Role.SALES)

    with raises_with(InvalidStateError, LAST_ADMIN):
        await change_role.execute(user_id=boss.id, role=Role.SALES, actor=DEV_ACTOR)

    assert await _role_of(uow_factory, boss.id) is Role.ADMIN


async def test_change_user_role_allows_demoting_an_admin_while_another_remains(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "boss", Role.ADMIN)

    await change_role.execute(user_id=other.id, role=Role.SALES, actor=root.to_principal())

    assert await _role_of(uow_factory, other.id) is Role.SALES


async def test_change_user_role_counts_only_active_admins(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await seed_user(uow_factory, "old-admin", Role.ADMIN, resigned=True)

    with raises_with(InvalidStateError, LAST_ADMIN):
        await change_role.execute(user_id=boss.id, role=Role.USER, actor=DEV_ACTOR)


async def test_change_user_role_refuses_resigned_user(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    gone = await seed_user(uow_factory, "gone", Role.SALES, resigned=True)

    with raises_with(InvalidStateError, RESIGNED):
        await change_role.execute(user_id=gone.id, role=Role.USER, actor=root.to_principal())

    assert await _role_of(uow_factory, gone.id) is Role.SALES


@pytest.mark.parametrize(
    ("login_id", "role"),
    [("dev-admin", Role.ADMIN), ("dev-sales", Role.SALES), ("dev-user", Role.USER)],
)
async def test_change_user_role_refuses_dev_login_users(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory, login_id: str, role: Role
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    target = await seed_user(uow_factory, login_id, role)
    new_role = Role.USER if role is not Role.USER else Role.SALES

    with raises_with(InvalidStateError, DEV_ONLY):
        await change_role.execute(user_id=target.id, role=new_role, actor=root.to_principal())

    assert await _role_of(uow_factory, target.id) is role


async def test_change_user_role_with_same_role_does_not_write(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    clock.advance(600)

    result = await change_role.execute(
        user_id=target.id, role=Role.SALES, actor=root.to_principal()
    )

    assert result.role is Role.SALES
    assert result.updated_at == target.updated_at
    async with uow_factory() as active:
        assert (await active.users.get(target.id)).updated_at == target.updated_at


async def test_change_user_role_with_unknown_id_is_not_found(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)

    with pytest.raises(UserNotFoundError):
        await change_role.execute(
            user_id=UserId(new_id()), role=Role.USER, actor=root.to_principal()
        )


async def test_change_user_role_leaves_other_users_unchanged(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    lee = await seed_user(uow_factory, "lee", Role.SALES)

    await change_role.execute(user_id=target.id, role=Role.USER, actor=root.to_principal())

    assert await _role_of(uow_factory, lee.id) is Role.SALES
    assert await _role_of(uow_factory, root.id) is Role.ADMIN
