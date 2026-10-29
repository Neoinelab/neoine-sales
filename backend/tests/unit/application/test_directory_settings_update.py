"""AD 설정 저장 UpdateDirectorySettings (AC4~AC6·AC10·AC12).

저장 전에 서비스 계정으로 Base DN을 찾고, 요청 admin이 새 설정으로 검색·바인드되는지 확인한다.
바인드 비밀번호는 암호화해 저장하며, 비우면 저장된 값을 쓴다(서버·계정이 같을 때만).
expected_revision=None은 설정이 아직 없을 때 새로 만든다.
"""

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
from app.domain.common.errors import InvalidStateError, InvalidValueError, NotFoundError
from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_auth import BASE_DN, BIND_PASSWORD, WRONG_PASSWORD, make_principal
from tests.factories_directory import make_directory_connection
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD, DEV_ACTOR, build_admin_stack
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import account_key, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import StoredDirectorySettings
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FixedClock

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


async def _update(
    admin: AdminStack,
    *,
    expected_revision: int | None = 1,
    password: str | None = ADMIN_PASSWORD,
    draft: DirectorySettingsDraft | None = None,
    actor: object = ADMIN_ACTOR,
) -> StoredDirectorySettings:
    return await admin.update_settings.execute(
        actor=actor,  # type: ignore[arg-type]
        draft=draft or _draft(),
        expected_revision=expected_revision,
        password=None if password is None else Password(password),
        client_ip=IP,
    )


async def _stored(uow_factory: UnitOfWorkFactory) -> StoredDirectorySettings | None:
    async with uow_factory() as uow:
        return await uow.directory_settings.get()


async def test_update_verifies_the_actor_with_the_discovered_base_dn_then_saves(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    await seed_directory(uow_factory)
    directory.base_dn = "dc=found,dc=test"

    stored = await _update(admin)

    (call,) = directory.authenticate_calls
    assert (call.base_dn, call.login_id.value, call.password) == (
        "dc=found,dc=test",
        "root",
        ADMIN_PASSWORD,
    )
    assert call.settings.connection == NEW_CONNECTION
    assert (stored.connection, stored.base_dn, stored.revision, stored.updated_by) == (
        NEW_CONNECTION,
        "dc=found,dc=test",
        2,
        ADMIN_ACTOR.user_id,
    )
    assert auth.cipher.unseal(stored.sealed_bind_password) == NEW_PASSWORD
    assert NEW_PASSWORD not in stored.sealed_bind_password.token
    assert await _stored(uow_factory) == stored


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
async def test_update_verification_failure_saves_nothing_and_reports_the_stage(  # noqa: PLR0913, PLR0917
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
    raise_in: str,
    error: Exception,
    stage: VerificationStage,
) -> None:
    before = await seed_directory(uow_factory)
    if raise_in == "discover":
        directory.discover_fails_with = error  # type: ignore[assignment]
    else:
        directory.authenticate_fails_with = error  # type: ignore[assignment]

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
    assert directory.discover_calls == []
    assert await _stored(uow_factory) == before


async def test_update_requires_a_password_from_a_directory_admin(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)

    with pytest.raises(InvalidValueError):
        await _update(admin, password=None)

    assert directory.authenticate_calls == []
    assert await _stored(uow_factory) == before


async def test_a_dev_admin_update_only_discovers_the_base_dn_and_records_the_dev_users_id(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    stored = await _update(admin, actor=DEV_ACTOR, password=None)

    assert len(directory.discover_calls) == 1
    assert directory.authenticate_calls == []
    assert (stored.revision, stored.updated_by, stored.base_dn) == (2, DEV_ACTOR.user_id, BASE_DN)


@pytest.mark.parametrize("subject", ["dev-admin2", "dev-adminx", "xdev-admin", "dev-sales2"])
async def test_the_discover_only_path_is_limited_to_the_reserved_dev_login_ids(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
    subject: str,
) -> None:
    await seed_directory(uow_factory)
    lookalike = make_principal(subject, Role.ADMIN)

    with pytest.raises(InvalidValueError):  # 예약 아이디가 아니면 비밀번호 없이는 통과하지 못한다
        await _update(admin, actor=lookalike, password=None)

    assert directory.authenticate_calls == []


async def test_a_dev_admin_update_with_a_failing_discovery_saves_nothing(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)
    directory.discover_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    with pytest.raises(DirectoryVerificationError) as caught:
        await _update(admin, actor=DEV_ACTOR, password=None)

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

    with pytest.raises(InvalidValueError):  # 비밀번호 없이는 admin 검색·바인드로 갈 수 없다
        await _update(strict, actor=DEV_ACTOR, password=None)

    assert directory.authenticate_calls == []
    assert await _stored(uow_factory) == before


async def test_update_keeps_existing_sessions_alive(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    issued = outcome.session

    await _update(admin)

    assert (await auth.authenticate.execute(issued.token)).subject == "kim"
    assert await session_is_active(uow_factory, issued.token)


async def test_update_without_bind_password_reuses_stored_password(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    before = await seed_directory(uow_factory)
    same_endpoint = make_directory_connection(
        user_filter="(uid={login_id})", connect_timeout_seconds=9
    )

    stored = await _update(admin, draft=_draft(same_endpoint, bind_password=None))

    assert directory.discover_calls[0].bind_password.reveal() == BIND_PASSWORD
    assert auth.cipher.unseal(stored.sealed_bind_password) == BIND_PASSWORD
    assert stored.connection == same_endpoint
    assert stored.revision == before.revision + 1


async def test_update_without_bind_password_after_host_change_is_rejected_before_contacting_ad(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)

    with pytest.raises(InvalidValueError) as caught:
        await _update(admin, draft=_draft(NEW_CONNECTION, bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []
    assert await _stored(uow_factory) == before


async def test_update_with_a_new_password_replaces_the_stored_one(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    stored = await _update(admin, draft=_draft(make_directory_connection(), NEW_PASSWORD))

    assert auth.cipher.unseal(stored.sealed_bind_password) == NEW_PASSWORD


async def test_update_with_unreadable_stored_password_needs_a_new_one(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    before = await seed_directory(uow_factory, unreadable=True)

    with pytest.raises(InvalidValueError) as caught:
        await _update(admin, draft=_draft(make_directory_connection(), bind_password=None))
    stored = await _update(admin, draft=_draft(make_directory_connection(), NEW_PASSWORD))

    assert "bind_password" in str(caught.value)
    assert before.revision == 1
    assert (stored.revision, auth.cipher.unseal(stored.sealed_bind_password)) == (2, NEW_PASSWORD)
    assert len(directory.discover_calls) == 1  # 거부된 요청은 AD에 묻지 않았다


async def test_update_with_null_revision_creates_settings_when_missing(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await _update(admin, expected_revision=None)

    assert (stored.revision, stored.updated_by, stored.base_dn) == (1, ADMIN_ACTOR.user_id, BASE_DN)
    assert auth.cipher.unseal(stored.sealed_bind_password) == NEW_PASSWORD
    assert await _stored(uow_factory) == stored


async def test_update_with_null_revision_conflicts_when_settings_exist(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    before = await seed_directory(uow_factory)

    with pytest.raises(DirectorySettingsConflictError):
        await _update(admin, expected_revision=None)

    assert directory.discover_calls == []
    assert await _stored(uow_factory) == before


async def test_update_with_an_integer_revision_is_not_found_when_settings_are_missing(
    admin: AdminStack,
) -> None:
    with pytest.raises(NotFoundError):
        await _update(admin, expected_revision=1)


async def test_update_with_null_revision_without_bind_password_is_rejected(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        await _update(admin, expected_revision=None, draft=_draft(bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []
    assert await _stored(uow_factory) is None


async def test_dev_admin_update_with_null_revision_only_discovers_the_base_dn(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    stored = await _update(admin, expected_revision=None, actor=DEV_ACTOR, password=None)

    assert (stored.revision, stored.updated_by) == (1, DEV_ACTOR.user_id)
    assert directory.authenticate_calls == []
    assert len(directory.discover_calls) == 1
