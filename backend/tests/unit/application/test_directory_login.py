"""DirectoryLogin 유스케이스(AUTH-1~6·13·14·7, T-U1~U6·U17·U18)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, LOGIN_FAILED
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW
from tests.factories_auth import make_directory_settings
from tests.fakes.auth_stack import SESSION_TTL
from tests.support.auth_seed import DUMMY_PASSWORD, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"


@pytest.fixture
async def ready(uow_factory: UnitOfWorkFactory) -> None:
    """AD 설정이 있고 kim(sales)이 등록된 상태."""
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)


async def _login(
    auth: AuthStack,
    login_id: str = "kim",
    password: str = "pw-kim",  # noqa: S107
) -> IssuedSession:
    return await auth.login.execute(login_id=login_id, password=Password(password), client_ip=IP)


@pytest.mark.usefixtures("ready")
async def test_login_issues_session_for_registered_user(auth: AuthStack, clock: FixedClock) -> None:
    issued = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert issued.principal.subject == "kim"
    assert issued.principal.role is Role.SALES
    assert issued.expires_at == NOW + SESSION_TTL
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"


@pytest.mark.usefixtures("ready")
async def test_login_role_comes_from_the_users_table(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "lee", Role.USER)
    auth.directory.add_account("lee", "pw-lee")

    issued = await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)

    assert issued.principal.role is Role.USER


@pytest.mark.usefixtures("ready")
async def test_login_succeeds_when_the_directory_display_name_is_256_chars(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.add_account("kim", "pw-kim", display_name="가" * 256, email="kim@corp.test")

    issued = await _login(auth)

    assert issued.principal.subject == "kim"
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"


@pytest.mark.usefixtures("ready")
async def test_login_updates_last_login_and_profile(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    await _login(auth)

    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.last_login_at == NOW
    assert user.display_name == "김영업"
    assert user.email == "kim@corp.test"


@pytest.mark.usefixtures("ready")
async def test_login_overwrites_profile_with_the_latest_directory_values(
    auth: AuthStack, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    await _login(auth)
    clock.advance(3600)
    auth.directory.add_account("kim", "pw-kim", display_name="김부장", email="kim2@corp.test")

    await _login(auth)

    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert (user.display_name, user.email) == ("김부장", "kim2@corp.test")
    assert user.last_login_at == clock.now()


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "case",
    ["wrong-password", "unknown-in-directory", "not-registered", "deleted", "malformed-id"],
)
async def test_login_failures_share_one_message_and_issue_no_session(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, case: str
) -> None:
    auth.directory.add_account("newbie", "pw-newbie")  # AD에는 있지만 앱에 등록되지 않음
    auth.directory.add_account("gone", "pw-gone")
    await seed_user(uow_factory, "gone", Role.SALES, deleted=True)
    attempts = {
        "wrong-password": ("kim", "not-the-password"),
        "unknown-in-directory": ("ghost", "pw-ghost"),
        "not-registered": ("newbie", "pw-newbie"),
        "deleted": ("gone", "pw-gone"),
        "malformed-id": ("kim)(uid=*", "pw-kim"),
    }
    login_id, password = attempts[case]

    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, login_id, password)

    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("ready")
async def test_login_failure_exception_never_contains_the_password(auth: AuthStack) -> None:
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, "kim", DUMMY_PASSWORD)

    chain = [caught.value, caught.value.__cause__, caught.value.__context__]
    for error in filter(None, chain):
        assert DUMMY_PASSWORD not in f"{error!s}{error!r}{error.args!r}"


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "error",
    [
        DirectoryUnavailableError(stage=VerificationStage.CONNECT),
        DirectoryUnavailableError(stage=VerificationStage.TLS),
        DirectoryMisconfiguredError(stage=VerificationStage.SEARCH),
    ],
)
async def test_directory_unavailable_is_propagated_and_not_counted(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork, error: Exception
) -> None:
    directory.fail_with = error  # type: ignore[assignment]

    with pytest.raises(DirectoryUnavailableError):
        await _login(auth)

    assert uow.login_failures._items == {}
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("ready")
async def test_login_id_is_normalized_before_lookup(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    issued = await auth.login.execute(login_id="  Kim ", password=Password("pw-kim"), client_ip=IP)

    assert issued.principal.subject == "kim"
    assert [call.login_id for call in directory.authenticate_calls] == [LoginId("kim")]


async def test_login_without_directory_settings_is_rejected_without_calling_directory(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await _login(auth)

    assert str(caught.value) == DIRECTORY_NOT_CONFIGURED
    assert directory.authenticate_calls == []
    assert uow.login_failures._items == {}


@pytest.mark.usefixtures("ready")
async def test_login_uses_the_current_settings_each_time(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, directory: FakeDirectoryAuthenticator
) -> None:
    await _login(auth)
    changed = make_directory_settings(base_dn="dc=other,dc=test")
    async with uow_factory() as uow:
        await uow.directory_settings.save(changed, expected_revision=1, updated_by="x", now=NOW)
        await uow.commit()

    await _login(auth)

    first, second = directory.authenticate_calls
    assert first.settings.base_dn == "dc=corp,dc=test"
    assert second.settings == changed


@pytest.mark.usefixtures("ready")
async def test_login_passes_the_password_only_to_the_directory(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    directory.add_account("kim", DUMMY_PASSWORD)

    issued = await _login(auth, "kim", DUMMY_PASSWORD)

    assert directory.authenticate_calls[0].password == DUMMY_PASSWORD
    stored = repr(uow.users._items) + repr(uow.sessions._items) + repr(uow.login_failures._items)
    assert DUMMY_PASSWORD not in stored
    assert DUMMY_PASSWORD not in repr(issued)
