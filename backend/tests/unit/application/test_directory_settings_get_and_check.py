"""AD 설정 조회·연결 테스트 GetDirectorySettings, TestDirectorySettings (SET-1·4·6·8, T-U36·U38)."""

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
from tests.factories_auth import WRONG_PASSWORD, make_directory_settings
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD, DEV_ACTOR
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.auth_seed import account_key, seed_directory

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.directory import FakeDirectoryAuthenticator

IP = "10.0.0.1"
NEW = make_directory_settings(base_dn="dc=new,dc=test")


async def _test(admin: AdminStack, password: str | None = ADMIN_PASSWORD) -> object:
    return await admin.test_settings.execute(
        actor=ADMIN_ACTOR,
        settings=NEW,
        password=None if password is None else Password(password),
        client_ip=IP,
    )


async def test_get_settings_returns_the_stored_row(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)

    assert await admin.get_settings.execute() == stored


async def test_get_settings_without_a_row_is_not_found(admin: AdminStack) -> None:
    with pytest.raises(NotFoundError):
        await admin.get_settings.execute()


async def test_test_settings_authenticates_the_admin_with_the_candidate_settings(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    result = await _test(admin)

    (call,) = directory.authenticate_calls
    assert (call.settings, call.login_id.value, call.password) == (NEW, "root", ADMIN_PASSWORD)
    assert result.success is True  # type: ignore[attr-defined]
    assert result.stage is None  # type: ignore[attr-defined]
    assert result.message  # type: ignore[attr-defined]


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

    assert result.success is False  # type: ignore[attr-defined]
    assert result.stage == VerificationStage.BIND  # type: ignore[attr-defined]
    assert result.message  # type: ignore[attr-defined]
    assert WRONG_PASSWORD not in result.message  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("error", "stage"),
    [
        (DirectoryUnavailableError(stage=VerificationStage.CONNECT), VerificationStage.CONNECT),
        (DirectoryUnavailableError(stage=VerificationStage.TLS), VerificationStage.TLS),
        (DirectoryMisconfiguredError(stage=VerificationStage.SEARCH), VerificationStage.SEARCH),
        (InvalidCredentialsError(stage=VerificationStage.BIND), VerificationStage.BIND),
    ],
)
async def test_test_settings_reports_each_failure_stage_without_raising(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    error: Exception,
    stage: VerificationStage,
) -> None:
    directory.fail_with = error  # type: ignore[assignment]

    result = await _test(admin)

    assert result.success is False  # type: ignore[attr-defined]
    assert result.stage == stage  # type: ignore[attr-defined]
    assert result.message  # type: ignore[attr-defined]


async def test_test_settings_without_a_password_is_invalid_and_skips_the_directory(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    with pytest.raises(InvalidValueError):
        await _test(admin, None)

    assert directory.authenticate_calls == []
    assert directory.probe_calls == []


async def test_a_dev_admin_test_only_probes_the_candidate_settings(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    result = await admin.test_settings.execute(
        actor=DEV_ACTOR, settings=NEW, password=None, client_ip=IP
    )

    assert directory.probe_calls == [NEW]
    assert directory.authenticate_calls == []
    assert result.success is True


async def test_a_dev_admin_test_reports_probe_failure_with_its_stage(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.probe_fails_with = DirectoryUnavailableError(stage=VerificationStage.TLS)

    result = await admin.test_settings.execute(
        actor=DEV_ACTOR, settings=NEW, password=None, client_ip=IP
    )

    assert (result.success, result.stage) == (False, VerificationStage.TLS)


async def test_a_dev_admin_ignores_a_supplied_password_and_still_only_probes(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    await admin.test_settings.execute(
        actor=DEV_ACTOR, settings=NEW, password=Password("whatever"), client_ip=IP
    )

    assert directory.authenticate_calls == []
    assert directory.probe_calls == [NEW]


async def test_bind_failures_count_toward_the_admins_attempt_limit(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    for _ in range(MAX_PER_ACCOUNT):
        await _test(admin, WRONG_PASSWORD)
    async with uow_factory() as uow:
        counter = await uow.login_failures.get_for_update(account_key("root"))
    calls = len(directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await _test(admin)  # 올바른 비밀번호도 잠금 중에는 AD를 부르지 않는다

    assert counter is not None
    assert counter.failures == MAX_PER_ACCOUNT
    assert len(directory.authenticate_calls) == calls


async def test_connection_failures_do_not_count_toward_the_attempt_limit(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    directory.fail_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)
    for _ in range(MAX_PER_ACCOUNT + 1):
        await _test(admin)
    directory.fail_with = None

    result = await _test(admin)

    assert result.success is True  # type: ignore[attr-defined]
