"""세션 인증(Authenticate)·DevLogin·IssueSession·Logout (AUTH-10~12, AC4, T14·T27)."""

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from app.application.auth.dev_login import DEV_LOGIN_IDS
from app.application.auth.tokens import hash_token
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserStatusFilter
from tests.factories import NOW
from tests.factories_auth import make_principal
from tests.fakes.auth_stack import SESSION_TTL, build_auth_stack
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def test_token_authenticates_the_registered_user_until_it_expires(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(user.to_principal())

    principal = await auth.authenticate.execute(issued.token)
    clock.advance(int(SESSION_TTL.total_seconds()))

    assert principal.subject == "kim"
    assert principal.user_id == user.id
    assert issued.expires_at == NOW + SESSION_TTL
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_role_is_read_from_the_users_table_on_every_request(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    forged = replace(user.to_principal(), role=Role.ADMIN)  # 세션에 적힌 역할은 무시된다
    issued = await auth.issue.execute(forged)

    assert (await auth.authenticate.execute(issued.token)).role is Role.SALES
    async with uow_factory() as uow:
        stored = await uow.users.get_active_by_login_id(LoginId("kim"))
        assert stored is not None
        stored.role = Role.USER
        await uow.users.update(stored)
        await uow.commit()

    assert (await auth.authenticate.execute(issued.token)).role is Role.USER


async def test_profile_comes_from_the_users_table(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    async with uow_factory() as uow:
        user.record_login(NOW, display_name="김영업", email="kim@corp.test")
        await uow.users.update(user)
        await uow.commit()
    issued = await auth.issue.execute(user.to_principal())

    principal = await auth.authenticate.execute(issued.token)

    assert (principal.name, principal.email) == ("김영업", "kim@corp.test")


async def test_physically_deleted_users_session_is_rejected_from_the_next_request(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(user.to_principal())
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"
    async with uow_factory() as uow:
        await uow.users.delete(user.id)
        await uow.commit()

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_resigned_users_token_is_rejected_even_if_the_session_row_survives(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(user.to_principal())
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
        stored.resign(NOW)
        await uow.users.update(stored)
        await uow.commit()

    with pytest.raises(AuthenticationError) as caught:
        await auth.authenticate.execute(issued.token)

    assert type(caught.value) is AuthenticationError


async def test_a_new_active_row_with_the_same_login_id_does_not_revive_the_old_token(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """토큰은 login_id가 아니라 user id에 묶여 있다. 재등록된 새 행으로 넘어가지 않는다."""
    old = await seed_user(uow_factory, "kim", Role.SALES, resigned=True)
    await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(old.to_principal())

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_session_of_an_unregistered_user_is_rejected(auth: AuthStack) -> None:
    issued = await auth.issue.execute(make_principal("ghost"))

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_session_with_a_subject_that_is_not_a_login_id_is_unauthenticated(
    auth: AuthStack,
) -> None:
    issued = await auth.issue.execute(make_principal("Not A Login!"))

    with pytest.raises(AuthenticationError) as caught:
        await auth.authenticate.execute(issued.token)

    assert type(caught.value) is AuthenticationError


@pytest.mark.parametrize("role", list(Role))
async def test_dev_login_uses_a_reserved_login_id_and_authenticates_through_users(
    auth: AuthStack, role: Role
) -> None:
    issued = await auth.dev_login.execute(role)

    principal = await auth.authenticate.execute(issued.token)

    assert issued.principal.subject == f"dev-{role.value}"
    assert f"dev-{role.value}" in DEV_LOGIN_IDS
    assert (principal.subject, principal.role) == (f"dev-{role.value}", role)
    assert principal.user_id == issued.principal.user_id


@pytest.mark.parametrize("role", list(Role))
async def test_dev_login_creates_the_users_row_once_and_reuses_it(
    auth: AuthStack, uow: FakeUnitOfWork, role: Role
) -> None:
    first = await auth.dev_login.execute(role)
    second = await auth.dev_login.execute(role)

    assert first.principal.user_id == second.principal.user_id
    rows = await uow.users.list_users(status=UserStatusFilter.ALL)
    assert [(u.login_id.value, u.role) for u in rows] == [(f"dev-{role.value}", role)]
    assert rows[0].created_by_user_id == rows[0].id  # 스스로 등록한 행
    assert rows[0].display_name == f"개발 사용자({role.value})"


async def test_dev_login_after_the_dev_row_resigned_creates_a_new_row(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    old = await auth.dev_login.execute(Role.ADMIN)
    async with uow_factory() as active:
        row = await active.users.get(old.principal.user_id)
        row.resign(NOW)
        await active.users.update(row)
        await active.commit()

    new = await auth.dev_login.execute(Role.ADMIN)

    assert new.principal.user_id != old.principal.user_id
    old_row = await uow.users.get(old.principal.user_id)
    assert old_row.deleted_at == NOW  # 옛 행은 그대로 퇴사 상태
    await auth.authenticate.execute(new.token)
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(old.token)


async def test_only_the_hash_of_the_token_is_stored(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    issued = await auth.dev_login.execute(Role.SALES)

    assert await uow.sessions.get_by_token_hash(issued.token) is None
    assert await uow.sessions.get_by_token_hash(hash_token(issued.token)) is not None


@pytest.mark.parametrize("token", [None, "", "unknown-token"])
async def test_missing_or_unknown_token_is_unauthenticated(
    auth: AuthStack, token: str | None
) -> None:
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)


async def test_tokens_are_unique(auth: AuthStack) -> None:
    first = await auth.dev_login.execute(Role.SALES)
    second = await auth.dev_login.execute(Role.SALES)

    assert first.token != second.token


async def test_logout_revokes_the_session(auth: AuthStack) -> None:
    issued = await auth.dev_login.execute(Role.SALES)

    await auth.logout.execute(issued.token)

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


@pytest.mark.parametrize("token", [None, "unknown"])
async def test_logout_is_idempotent_for_missing_sessions(
    auth: AuthStack, token: str | None
) -> None:
    await auth.logout.execute(token)


async def test_revoking_twice_is_harmless(auth: AuthStack) -> None:
    issued = await auth.dev_login.execute(Role.SALES)

    await auth.logout.execute(issued.token)
    await auth.logout.execute(issued.token)

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_dev_user_session_is_rejected_when_dev_users_are_not_allowed(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, directory: FakeDirectoryAuthenticator
) -> None:

    stack = build_auth_stack(uow_factory, clock, directory, allow_dev_sessions=False)
    issued = await stack.dev_login.execute(Role.SALES)

    with pytest.raises(AuthenticationError):
        await stack.authenticate.execute(issued.token)
