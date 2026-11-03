"""세션 인증(Authenticate)·IssueSession·Logout (AUTH-10~12, AC4, T14·T27)."""

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from app.application.auth.authenticate import Authenticate
from app.application.auth.tokens import hash_token
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.factories_auth import make_principal
from tests.fakes.auth_stack import SESSION_TTL
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _issue_for(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> IssuedSession:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    return await auth.issue.execute(user.to_principal())


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


async def test_only_the_hash_of_the_token_is_stored(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    issued = await _issue_for(auth, uow_factory)

    assert await uow.sessions.get_by_token_hash(issued.token) is None
    assert await uow.sessions.get_by_token_hash(hash_token(issued.token)) is not None


@pytest.mark.parametrize("token", [None, "", "unknown-token"])
async def test_missing_or_unknown_token_is_unauthenticated(
    auth: AuthStack, token: str | None
) -> None:
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)


async def test_tokens_are_unique(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> None:
    first = await _issue_for(auth, uow_factory)
    second = await auth.issue.execute(first.principal)

    assert first.token != second.token


async def test_logout_revokes_the_session(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> None:
    issued = await _issue_for(auth, uow_factory)

    await auth.logout.execute(issued.token)

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


@pytest.mark.parametrize("token", [None, "unknown"])
async def test_logout_is_idempotent_for_missing_sessions(
    auth: AuthStack, token: str | None
) -> None:
    await auth.logout.execute(token)


async def test_revoking_twice_is_harmless(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> None:
    issued = await _issue_for(auth, uow_factory)

    await auth.logout.execute(issued.token)
    await auth.logout.execute(issued.token)

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


def test_authenticate_has_no_switch_to_allow_dev_users(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(TypeError):
        Authenticate(uow_factory, clock, allow_dev_users=True)  # type: ignore[call-arg]
