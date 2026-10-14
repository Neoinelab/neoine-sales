"""최초 설정 2단계 SetupFirstAdmin (SETUP-4~8, T-U23~U26)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_FIRST, LOGIN_FAILED, SETUP_CLOSED
from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError
from tests.factories import NOW
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.auth_seed import account_key, active_admin_logins, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"


async def _setup(
    auth: AuthStack,
    login_id: str = "kim",
    password: str = "pw-kim",  # noqa: S107
) -> IssuedSession:
    return await auth.setup_admin.execute(
        login_id=login_id, password=Password(password), client_ip=IP
    )


async def test_setup_admin_requires_directory_first(auth: AuthStack) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == DIRECTORY_FIRST
    assert auth.directory.authenticate_calls == []


async def test_setup_admin_registers_admin_and_signs_in(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)

    issued = await _setup(auth, "  Kim ")

    assert (issued.principal.subject, issued.principal.role) == ("kim", Role.ADMIN)
    assert (await auth.authenticate.execute(issued.token)).role is Role.ADMIN
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.role is Role.ADMIN
    assert user.created_by_user_id == user.id  # 최초 admin은 자기 자신이 등록자
    assert issued.principal.user_id == user.id
    assert user.last_login_at == NOW
    assert (user.display_name, user.email) == ("김영업", "kim@corp.test")
    assert uow.users.roster_locks >= 1


async def test_setup_admin_authenticates_with_the_stored_settings(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)

    await _setup(auth)

    assert auth.directory.authenticate_calls[0].settings == stored.settings


async def test_setup_admin_after_admin_exists_is_rejected_without_calling_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == SETUP_CLOSED
    assert auth.directory.authenticate_calls == []
    assert await active_admin_logins(uow_factory) == ["boss"]


async def test_setup_admin_wrong_password_is_the_login_failure_and_registers_nobody(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)

    with pytest.raises(AuthenticationError) as caught:
        await _setup(auth, "kim", "wrong")

    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert await active_admin_logins(uow_factory) == []
    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_setup_admin_malformed_id_is_the_login_failure(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    with pytest.raises(AuthenticationError) as caught:
        await _setup(auth, "kim)(uid=*")

    assert str(caught.value) == LOGIN_FAILED
    assert auth.directory.authenticate_calls == []


async def test_setup_admin_is_throttled_like_login(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(AuthenticationError):
            await _setup(auth, "kim", "wrong")
    calls_before = len(auth.directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await _setup(auth)

    assert len(auth.directory.authenticate_calls) == calls_before


async def test_setup_admin_directory_outage_is_propagated_and_not_counted(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)
    auth.directory.fail_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    with pytest.raises(DirectoryUnavailableError):
        await _setup(auth)

    assert uow.login_failures._items == {}
    assert await active_admin_logins(uow_factory) == []


async def test_setup_admin_success_clears_the_failure_counter(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)
    with pytest.raises(AuthenticationError):
        await _setup(auth, "kim", "wrong")

    await _setup(auth)

    assert account_key("kim") not in uow.login_failures._items


async def test_setup_admin_rechecks_admin_after_directory_authentication(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """AD 인증 도중 다른 요청이 admin을 만들면 잠금 뒤 재확인에서 막힌다(admin 1명 유지)."""
    await seed_directory(uow_factory)

    async def other_admin_registers_meanwhile() -> None:
        await seed_user(uow_factory, "boss", Role.ADMIN)

    auth.directory.on_authenticate = other_admin_registers_meanwhile

    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == SETUP_CLOSED
    assert await active_admin_logins(uow_factory) == ["boss"]
    assert uow.sessions._items == {}


async def test_setup_admin_rejects_an_existing_active_user_with_the_same_login_id(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)

    with pytest.raises((AlreadyExistsError, InvalidStateError)):
        await _setup(auth)

    assert await active_admin_logins(uow_factory) == []
    async with uow_factory() as uow:
        existing = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert existing is not None
    assert existing.role is Role.SALES
