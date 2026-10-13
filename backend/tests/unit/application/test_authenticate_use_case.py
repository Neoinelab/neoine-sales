"""세션 인증(Authenticate)·DevLogin·IssueSession·Logout (AUTH-10~12, T-U12~U15)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.tokens import hash_token
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Principal, Role
from tests.factories import NOW
from tests.fakes.auth_stack import SESSION_TTL, build_auth_stack
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


def _principal(subject: str, role: Role = Role.SALES) -> Principal:
    return Principal(subject, None, subject, role)


async def test_token_authenticates_the_registered_user_until_it_expires(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(_principal("kim"))

    principal = await auth.authenticate.execute(issued.token)
    clock.advance(int(SESSION_TTL.total_seconds()))

    assert principal.subject == "kim"
    assert issued.expires_at == NOW + SESSION_TTL
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_role_is_read_from_the_users_table_on_every_request(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(_principal("kim", Role.ADMIN))  # 세션에 적힌 역할은 무시된다

    assert (await auth.authenticate.execute(issued.token)).role is Role.SALES
    async with uow_factory() as uow:
        user = await uow.users.get_active_by_login_id(LoginId("kim"))
        assert user is not None
        user.role = Role.USER
        await uow.users.update(user)
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
    issued = await auth.issue.execute(_principal("kim"))

    principal = await auth.authenticate.execute(issued.token)

    assert (principal.name, principal.email) == ("김영업", "kim@corp.test")


async def test_deleted_users_session_is_rejected_from_the_next_request(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(_principal("kim"))
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"
    async with uow_factory() as uow:
        await uow.users.delete(user.id)
        await uow.commit()

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_session_of_an_unregistered_subject_is_rejected(auth: AuthStack) -> None:
    issued = await auth.issue.execute(_principal("ghost"))

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_session_with_a_subject_that_is_not_a_login_id_is_unauthenticated(
    auth: AuthStack,
) -> None:
    issued = await auth.issue.execute(_principal("Not A Login!"))

    with pytest.raises(AuthenticationError) as caught:
        await auth.authenticate.execute(issued.token)

    assert type(caught.value) is AuthenticationError


@pytest.mark.parametrize("role", list(Role))
async def test_dev_login_subject_is_dev_colon_role_and_passes_when_allowed(
    auth: AuthStack, role: Role
) -> None:
    issued = await auth.dev_login.execute(role)

    principal = await auth.authenticate.execute(issued.token)

    assert issued.principal.subject == f"dev:{role.value}"
    assert (principal.subject, principal.role) == (f"dev:{role.value}", role)


@pytest.mark.parametrize("role", list(Role))
async def test_dev_sessions_are_rejected_when_not_allowed(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, role: Role
) -> None:
    stack = build_auth_stack(uow_factory, clock, allow_dev_sessions=False)
    issued = await stack.dev_login.execute(role)

    with pytest.raises(AuthenticationError) as caught:
        await stack.authenticate.execute(issued.token)

    assert type(caught.value) is AuthenticationError


async def test_dev_session_needs_no_users_row(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    issued = await auth.dev_login.execute(Role.ADMIN)

    await auth.authenticate.execute(issued.token)

    assert uow.users._items == {}


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
