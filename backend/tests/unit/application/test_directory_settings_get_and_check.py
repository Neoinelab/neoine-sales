"""AD 설정 조회·연결 테스트 GetDirectorySettings, TestDirectorySettings (AC3~AC6·AC10).

연결 테스트는 서비스 계정으로 Base DN을 찾고, 요청 admin이 새 설정으로 검색·바인드되는지 본다.
저장하지 않으며 실패는 예외 대신 결과(단계·안내)로 돌려준다. 비밀번호 입력 규칙 위반은 예외다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import Password
from app.domain.auth.errors import TooManyAttemptsError
from app.domain.common.errors import InvalidValueError, NotFoundError
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_auth import BASE_DN, BIND_PASSWORD, WRONG_PASSWORD
from tests.factories_directory import make_directory_connection
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD, DEV_ACTOR
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.auth_seed import account_key, seed_directory

if TYPE_CHECKING:
    from app.application.directory.test_settings import TestResult
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.directory import FakeDirectoryAuthenticator

IP = "10.0.0.1"
NEW_CONNECTION = make_directory_connection(host="dc2.corp.test")
NEW_PASSWORD = "New-bind-pw-2!"  # noqa: S105 - 가짜 값


def _draft(
    connection: object = NEW_CONNECTION, bind_password: str | None = NEW_PASSWORD
) -> DirectorySettingsDraft:
    return DirectorySettingsDraft(
        connection=connection,  # type: ignore[arg-type]
        bind_password=None if bind_password is None else Password(bind_password),
    )


async def _test(
    admin: AdminStack,
    password: str | None = ADMIN_PASSWORD,
    draft: DirectorySettingsDraft | None = None,
) -> TestResult:
    return await admin.test_settings.execute(
        actor=ADMIN_ACTOR,
        draft=draft or _draft(),
        password=None if password is None else Password(password),
        client_ip=IP,
    )


async def test_get_settings_returns_the_stored_row_and_a_readable_credential(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)

    view = await admin.get_settings.execute()

    assert view.stored == stored
    assert view.credential_readable is True
    assert BIND_PASSWORD not in repr(view)


async def test_get_settings_reports_unreadable_credential(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """키가 바뀌어 저장된 비밀번호를 풀 수 없어도 조회는 성공하고 상태만 알린다(AC10)."""
    stored = await seed_directory(uow_factory, unreadable=True)

    view = await admin.get_settings.execute()

    assert view.stored == stored
    assert view.credential_readable is False


async def test_get_settings_without_a_row_is_not_found(admin: AdminStack) -> None:
    with pytest.raises(NotFoundError):
        await admin.get_settings.execute()


async def test_test_settings_discovers_base_dn_then_authenticates_the_admin(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    directory.base_dn = "dc=found,dc=test"

    result = await _test(admin)

    (discovered,) = directory.discover_calls
    assert discovered.connection == NEW_CONNECTION
    assert discovered.bind_password.reveal() == NEW_PASSWORD
    (call,) = directory.authenticate_calls
    assert (call.base_dn, call.login_id.value, call.password) == (
        "dc=found,dc=test",
        "root",
        ADMIN_PASSWORD,
    )
    assert call.settings == discovered
    assert result.success is True
    assert result.stage is None
    assert result.message
    assert result.base_dn == "dc=found,dc=test"


async def test_test_settings_returns_discovered_base_dn_on_success(admin: AdminStack) -> None:
    result = await _test(admin)

    assert result.base_dn == BASE_DN


async def test_test_settings_never_saves(admin: AdminStack, uow_factory: UnitOfWorkFactory) -> None:
    # 시도 선점(로그인 시도 제한)은 커밋하므로 커밋 횟수가 아니라 저장된 설정이 그대로인지 본다.
    before = await seed_directory(uow_factory)

    await _test(admin)

    async with uow_factory() as active:
        assert await active.directory_settings.get() == before


async def test_test_settings_reports_a_wrong_password_as_a_bind_failure_result(
    admin: AdminStack,
) -> None:
    result = await _test(admin, WRONG_PASSWORD)

    assert result.success is False
    assert result.stage == VerificationStage.BIND
    assert result.base_dn is None
    assert result.message
    assert WRONG_PASSWORD not in result.message


@pytest.mark.parametrize(
    ("raise_in", "error", "stage"),
    [
        (
            "discover",
            DirectoryUnavailableError(stage=VerificationStage.CONNECT),
            VerificationStage.CONNECT,
        ),
        ("discover", DirectoryUnavailableError(stage=VerificationStage.TLS), VerificationStage.TLS),
        (
            "discover",
            DirectoryMisconfiguredError(stage=VerificationStage.SERVICE_BIND),
            VerificationStage.SERVICE_BIND,
        ),
        (
            "discover",
            DirectoryMisconfiguredError(stage=VerificationStage.BASE_DN),
            VerificationStage.BASE_DN,
        ),
        (
            "authenticate",
            InvalidCredentialsError(stage=VerificationStage.SEARCH),
            VerificationStage.SEARCH,
        ),
        (
            "authenticate",
            DirectoryMisconfiguredError(stage=VerificationStage.SEARCH),
            VerificationStage.SEARCH,
        ),
        (
            "authenticate",
            InvalidCredentialsError(stage=VerificationStage.BIND),
            VerificationStage.BIND,
        ),
        (
            "authenticate",
            DirectoryUnavailableError(stage=VerificationStage.CONNECT),
            VerificationStage.CONNECT,
        ),
    ],
)
async def test_test_settings_reports_each_failure_stage_without_raising(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    raise_in: str,
    error: Exception,
    stage: VerificationStage,
) -> None:
    if raise_in == "discover":
        directory.discover_fails_with = error  # type: ignore[assignment]
    else:
        directory.authenticate_fails_with = error  # type: ignore[assignment]

    result = await _test(admin)

    assert result.success is False
    assert result.stage == stage
    assert result.base_dn is None
    assert result.message


async def test_test_settings_does_not_authenticate_when_base_dn_discovery_fails(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.discover_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    await _test(admin)

    assert directory.authenticate_calls == []


async def test_test_settings_without_an_admin_password_is_invalid_and_skips_the_admin_bind(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    with pytest.raises(InvalidValueError):
        await _test(admin, None)

    assert directory.authenticate_calls == []


async def test_a_dev_admin_test_only_discovers_the_base_dn(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    result = await admin.test_settings.execute(
        actor=DEV_ACTOR, draft=_draft(), password=None, client_ip=IP
    )

    assert len(directory.discover_calls) == 1
    assert directory.authenticate_calls == []
    assert result.success is True
    assert result.base_dn == BASE_DN


async def test_a_dev_admin_test_reports_discovery_failure_with_its_stage(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.discover_fails_with = DirectoryUnavailableError(stage=VerificationStage.TLS)

    result = await admin.test_settings.execute(
        actor=DEV_ACTOR, draft=_draft(), password=None, client_ip=IP
    )

    assert (result.success, result.stage, result.base_dn) == (False, VerificationStage.TLS, None)


async def test_a_dev_admin_ignores_a_supplied_password_and_still_only_discovers(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    await admin.test_settings.execute(
        actor=DEV_ACTOR, draft=_draft(), password=Password("whatever"), client_ip=IP
    )

    assert directory.authenticate_calls == []
    assert len(directory.discover_calls) == 1


async def test_bind_failures_count_toward_the_admins_attempt_limit(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    for _ in range(MAX_PER_ACCOUNT):
        await _test(admin, WRONG_PASSWORD)
    async with uow_factory() as uow:
        counter = await uow.login_failures.get_for_update(account_key("root"))
    calls = len(directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await _test(admin)  # 올바른 비밀번호도 잠금 중에는 AD 인증을 부르지 않는다

    assert counter is not None
    assert counter.failures == MAX_PER_ACCOUNT
    assert len(directory.authenticate_calls) == calls


async def test_connection_failures_do_not_count_toward_the_attempt_limit(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.authenticate_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)
    for _ in range(MAX_PER_ACCOUNT + 1):
        await _test(admin)
    directory.authenticate_fails_with = None

    result = await _test(admin)

    assert result.success is True


async def test_test_settings_without_bind_password_uses_the_stored_one(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)
    keep = _draft(make_directory_connection(user_filter="(uid={login_id})"), bind_password=None)

    result = await _test(admin, draft=keep)

    assert result.success is True
    assert directory.discover_calls[0].bind_password.reveal() == BIND_PASSWORD
    assert directory.discover_calls[0].connection.host == stored.connection.host


async def test_test_settings_without_bind_password_after_host_change_is_rejected_before_ad(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    with pytest.raises(InvalidValueError) as caught:
        await _test(admin, draft=_draft(NEW_CONNECTION, bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []


async def test_test_settings_without_bind_password_and_no_stored_settings_is_rejected(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        await _test(admin, draft=_draft(make_directory_connection(), bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []


async def test_test_settings_without_bind_password_and_unreadable_stored_one_is_rejected(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory, unreadable=True)

    with pytest.raises(InvalidValueError) as caught:
        await _test(admin, draft=_draft(make_directory_connection(), bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []


async def test_test_settings_with_a_new_password_works_when_the_stored_one_is_unreadable(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory, unreadable=True)

    result = await _test(admin, draft=_draft(make_directory_connection(), NEW_PASSWORD))

    assert result.success is True
