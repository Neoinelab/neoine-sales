"""사용자 삭제 DeleteUser: 연결이 없으면 물리 삭제, 보호 규칙 (AC3·5, USER-4~7, T11·T15)."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.auth.tokens import hash_token
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
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


async def test_delete_user_without_links_removes_the_row_physically(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.DELETED
    assert await active_logins(uow_factory) == ["root"]
    async with uow_factory() as uow:
        with pytest.raises(UserNotFoundError):
            await uow.users.get(target.id)


async def test_delete_outcome_values_are_stable_api_codes() -> None:
    assert {o.value for o in DeleteOutcome} == {"deleted", "resigned"}


async def test_delete_user_removes_every_session_row_of_that_user_only(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    lee = await seed_user(uow_factory, "lee", Role.SALES)
    first = (await auth.issue.execute(target.to_principal())).token
    second = (await auth.issue.execute(target.to_principal())).token
    other = (await auth.issue.execute(lee.to_principal())).token

    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert not await session_is_active(uow_factory, first)
    assert not await session_is_active(uow_factory, second)
    assert await session_is_active(uow_factory, other)
    async with (
        uow_factory() as uow
    ):  # 폐기가 아니라 행 삭제여야 FK 때문에 물리 삭제가 막히지 않는다
        assert await uow.sessions.get_by_token_hash(hash_token(first)) is None


async def test_deleting_a_user_blocks_the_session_immediately(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(target.to_principal())).token
    assert (await auth.authenticate.execute(token)).subject == "kim"

    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)


async def test_delete_user_refuses_to_delete_oneself(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    me = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    token = (await auth.issue.execute(me.to_principal())).token

    with pytest.raises(InvalidStateError, match="자기 자신"):
        await admin.delete_user.execute(user_id=me.id, actor=me.to_principal())

    assert await active_logins(uow_factory) == ["boss", "root"]
    assert await session_is_active(uow_factory, token)  # 거부되면 세션 삭제도 일어나지 않는다


async def test_delete_user_refuses_the_last_active_admin(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(boss.to_principal())).token

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
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "boss", Role.ADMIN)

    await admin.delete_user.execute(user_id=other.id, actor=root.to_principal())

    assert await active_logins(uow_factory) == ["root"]


async def test_an_actor_without_a_users_row_can_delete_a_sales_user(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    outcome = await admin.delete_user.execute(user_id=target.id, actor=DEV_ACTOR)

    assert outcome is DeleteOutcome.DELETED
    assert await active_logins(uow_factory) == ["boss"]


async def test_delete_user_with_unknown_id_is_not_found(admin: AdminStack) -> None:
    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=UserId(uuid4()), actor=ADMIN_ACTOR)


async def test_physically_deleted_user_is_not_found_the_second_time(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())


async def test_a_user_deleted_before_the_call_is_not_found(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    gone = await seed_user(uow_factory, "gone", Role.SALES, deleted=True)

    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=gone.id, actor=DEV_ACTOR)
