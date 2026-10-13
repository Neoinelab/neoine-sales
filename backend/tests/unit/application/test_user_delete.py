"""사용자 삭제 DeleteUser (USER-4~7, T-U29~U31)."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Principal, Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId
from tests.fakes.admin_stack import ADMIN_ACTOR, DEV_ACTOR
from tests.support.admin_seed import active_logins, session_is_active
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork


def _principal(login_id: str, role: Role) -> Principal:
    return Principal(login_id, None, login_id, role)


async def test_delete_user_removes_the_user_row(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)

    assert await active_logins(uow_factory) == ["root"]
    async with uow_factory() as uow:
        with pytest.raises(UserNotFoundError):
            await uow.users.get(target.id)


async def test_delete_user_revokes_every_session_of_that_user_only(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await seed_user(uow_factory, "lee", Role.SALES)
    kim = _principal("kim", Role.SALES)
    first = (await auth.issue.execute(kim)).token
    second = (await auth.issue.execute(kim)).token
    other = (await auth.issue.execute(_principal("lee", Role.SALES))).token

    await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)

    assert not await session_is_active(uow_factory, first)
    assert not await session_is_active(uow_factory, second)
    assert await session_is_active(uow_factory, other)


async def test_deleted_users_old_session_stays_dead_after_the_login_id_is_registered_again(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """세션 폐기가 없으면 같은 아이디로 재등록한 순간 이전 세션이 되살아난다."""
    await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    old_token = (await auth.issue.execute(_principal("kim", Role.SALES))).token

    await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)
    await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(old_token)


async def test_deleting_a_user_blocks_the_session_immediately(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(_principal("kim", Role.SALES))).token
    assert (await auth.authenticate.execute(token)).subject == "kim"

    await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)


async def test_delete_user_takes_the_roster_lock(
    admin: AdminStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    before = uow.users.roster_locks

    await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)

    assert uow.users.roster_locks == before + 1


async def test_delete_user_refuses_to_delete_oneself(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    me = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    token = (await auth.issue.execute(_principal("root", Role.ADMIN))).token

    with pytest.raises(InvalidStateError, match="자기 자신"):
        await admin.delete_user.execute(user_id=me.id, actor=ADMIN_ACTOR)

    assert await active_logins(uow_factory) == ["boss", "root"]
    assert await session_is_active(uow_factory, token)


async def test_delete_user_refuses_the_last_active_admin(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(_principal("boss", Role.ADMIN))).token

    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=boss.id, actor=DEV_ACTOR)

    assert await active_logins(uow_factory) == ["boss", "kim"]
    assert await session_is_active(uow_factory, token)


async def test_admin_count_drops_after_an_admin_is_deleted(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    old = await seed_user(uow_factory, "old-admin", Role.ADMIN)
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await admin.delete_user.execute(user_id=old.id, actor=DEV_ACTOR)

    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=boss.id, actor=DEV_ACTOR)


async def test_delete_user_allows_removing_an_admin_while_another_remains(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "boss", Role.ADMIN)

    await admin.delete_user.execute(user_id=other.id, actor=ADMIN_ACTOR)

    assert await active_logins(uow_factory) == ["root"]


async def test_the_remaining_admin_cannot_be_deleted_afterwards(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "boss", Role.ADMIN)
    await admin.delete_user.execute(user_id=other.id, actor=ADMIN_ACTOR)

    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=root.id, actor=DEV_ACTOR)


async def test_a_dev_admin_without_a_users_row_can_delete_a_sales_user(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    await admin.delete_user.execute(user_id=target.id, actor=DEV_ACTOR)

    assert await active_logins(uow_factory) == ["boss"]


async def test_delete_user_with_unknown_id_is_not_found(admin: AdminStack) -> None:
    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=UserId(uuid4()), actor=ADMIN_ACTOR)


async def test_delete_user_twice_is_not_found_the_second_time(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)

    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)


async def test_a_user_deleted_before_the_call_is_not_found(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    gone = await seed_user(uow_factory, "gone", Role.SALES, deleted=True)

    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=gone.id, actor=DEV_ACTOR)
