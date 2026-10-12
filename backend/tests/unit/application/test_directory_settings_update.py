"""AD 설정 저장 UpdateDirectorySettings (SET-2·3·5·6·8, T-U32~U35·U37~U39)."""

from typing import TYPE_CHECKING

import pytest

from app.application.directory.errors import DirectoryVerificationError
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import Password
from app.domain.auth.errors import TooManyAttemptsError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError, InvalidValueError
from tests.factories import NOW
from tests.factories_auth import WRONG_PASSWORD, make_directory_settings
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD, DEV_ACTOR, build_admin_stack
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import account_key, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FixedClock

IP = "10.0.0.1"
NEW = make_directory_settings(base_dn="dc=new,dc=test")


async def _update(
    admin: AdminStack,
    *,
    expected_revision: int = 1,
    password: str | None = ADMIN_PASSWORD,
    settings: DirectorySettings = NEW,
) -> StoredDirectorySettings:
    return await admin.update_settings.execute(
        actor=ADMIN_ACTOR,
        settings=settings,
        expected_revision=expected_revision,
        password=None if password is None else Password(password),
        client_ip=IP,
    )


async def _stored(uow_factory: UnitOfWorkFactory) -> StoredDirectorySettings | None:
    async with uow_factory() as uow:
        return await uow.directory_settings.get()


async def test_update_verifies_the_actor_with_the_new_settings_then_saves(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    stored = await _update(admin)

    (call,) = directory.authenticate_calls
    assert (call.settings, call.login_id.value, call.password) == (NEW, "root", ADMIN_PASSWORD)
    assert (stored.settings, stored.revision, stored.updated_by) == (NEW, 2, "root")
    assert await _stored(uow_factory) == stored


@pytest.mark.parametrize(
    ("error", "stage"),
    [
        (InvalidCredentialsError(stage=VerificationStage.BIND), VerificationStage.BIND),
        (DirectoryUnavailableError(stage=VerificationStage.CONNECT), VerificationStage.CONNECT),
        (DirectoryUnavailableError(stage=VerificationStage.TLS), VerificationStage.TLS),
        (DirectoryMisconfiguredError(stage=VerificationStage.SEARCH), VerificationStage.SEARCH),
    ],
)
async def test_update_verification_failure_saves_nothing_and_reports_the_stage(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
    error: Exception,
    stage: VerificationStage,
) -> None:
    before = await seed_directory(uow_factory)
    directory.fail_with = error  # type: ignore[assignment]

    with pytest.raises(DirectoryVerificationError) as caught:
        await _update(admin)

    assert caught.value.stage == stage
    assert caught.value.message
    assert await _stored(uow_factory) == before


async def test_update_with_a_wrong_password_keeps_the_old_settings(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)

    with pytest.raises(DirectoryVerificationError) as caught:
        await _update(admin, password=WRONG_PASSWORD)

    assert caught.value.stage == VerificationStage.BIND
    assert WRONG_PASSWORD not in str(caught.value)
    assert await _stored(uow_factory) == before


async def test_update_bind_failure_adds_one_failure_to_the_admins_counter(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    with pytest.raises(DirectoryVerificationError):
        await _update(admin, password=WRONG_PASSWORD)

    async with uow_factory() as uow:
        counter = await uow.login_failures.get_for_update(account_key("root"))
    assert counter is not None
    assert counter.failures == 1


async def test_update_is_refused_while_the_admin_is_locked_out(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(DirectoryVerificationError):
            await _update(admin, password=WRONG_PASSWORD)
    calls = len(directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await _update(admin)

    assert len(directory.authenticate_calls) == calls
    assert await _stored(uow_factory) == before


async def test_update_with_a_stale_revision_conflicts_without_calling_the_directory(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)

    with pytest.raises(InvalidStateError):
        await _update(admin, expected_revision=before.revision + 1)

    assert directory.authenticate_calls == []
    assert directory.probe_calls == []
    assert await _stored(uow_factory) == before


async def test_update_conflicts_when_another_save_lands_during_verification(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    rival = make_directory_settings(base_dn="dc=rival,dc=test")

    async def rival_saves_first() -> None:
        async with uow_factory() as uow:
            await uow.directory_settings.save(
                rival, expected_revision=1, updated_by="other-admin", now=NOW
            )
            await uow.commit()

    directory.on_authenticate = rival_saves_first

    with pytest.raises(InvalidStateError):
        await _update(admin)

    stored = await _stored(uow_factory)
    assert stored is not None
    assert (stored.settings, stored.revision, stored.updated_by) == (rival, 2, "other-admin")


async def test_update_requires_a_password_from_a_directory_admin(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)

    with pytest.raises(InvalidValueError):
        await _update(admin, password=None)

    assert directory.authenticate_calls == []
    assert directory.probe_calls == []
    assert await _stored(uow_factory) == before


async def test_a_dev_admin_update_only_probes_and_records_the_dev_subject(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    stored = await admin.update_settings.execute(
        actor=DEV_ACTOR, settings=NEW, expected_revision=1, password=None, client_ip=IP
    )

    assert directory.probe_calls == [NEW]
    assert directory.authenticate_calls == []
    assert (stored.revision, stored.updated_by) == (2, "dev:admin")


async def test_a_dev_admin_update_with_a_failing_probe_saves_nothing(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)
    directory.probe_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    with pytest.raises(DirectoryVerificationError) as caught:
        await admin.update_settings.execute(
            actor=DEV_ACTOR, settings=NEW, expected_revision=1, password=None, client_ip=IP
        )

    assert caught.value.stage == VerificationStage.CONNECT
    assert await _stored(uow_factory) == before


async def test_a_dev_subject_is_not_special_when_dev_sessions_are_not_allowed(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    directory: FakeDirectoryAuthenticator,
) -> None:
    strict = build_admin_stack(auth, uow_factory, clock, allow_dev_sessions=False)
    before = await seed_directory(uow_factory)

    with pytest.raises(InvalidValueError):  # 비밀번호 없이는 probe로 갈 수 없다
        await strict.update_settings.execute(
            actor=DEV_ACTOR, settings=NEW, expected_revision=1, password=None, client_ip=IP
        )

    assert directory.probe_calls == []
    assert await _stored(uow_factory) == before


async def test_update_keeps_existing_sessions_alive(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    await _update(admin)

    assert (await auth.authenticate.execute(issued.token)).subject == "kim"
    assert await session_is_active(uow_factory, issued.token)
