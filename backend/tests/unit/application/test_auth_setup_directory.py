"""최초 설정 1단계 RegisterSetupDirectory와 GetAuthStatus (AC5·AC6·AC11).

서비스 계정으로 바인드해 Base DN을 찾는 데까지만 확인한다(관리자 검색·바인드 단계는 없다).
바인드 비밀번호는 암호화해 저장하고 평문은 저장소에 남지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import SETUP_CLOSED
from app.application.directory.errors import DirectoryVerificationError
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories_auth import BASE_DN, BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.auth_seed import seed_directory, seed_storage, seed_user

if TYPE_CHECKING:
    from app.application.auth.auth_status import AuthStatus
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import StoredDirectorySettings
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

LEAK = "raw-server-banner-do-not-leak"


async def _stored(uow_factory: UnitOfWorkFactory) -> StoredDirectorySettings | None:
    async with uow_factory() as uow:
        return await uow.directory_settings.get()


async def test_auth_status_reports_each_setup_step(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """최초 설정은 3단계다(AD -> 저장 위치 -> admin). 전체 조합은 test_auth_status_storage."""
    empty = await auth.status.execute()
    await seed_directory(uow_factory)
    directory_only = await auth.status.execute()
    await seed_storage(uow_factory)
    directory_and_storage = await auth.status.execute()
    await seed_user(uow_factory, "boss", Role.ADMIN)
    done = await auth.status.execute()

    def flags(status: AuthStatus) -> tuple[bool, bool, bool]:
        return (status.needs_directory_setup, status.needs_storage_setup, status.needs_admin_setup)

    assert flags(empty) == (True, True, False)
    assert flags(directory_only) == (False, True, False)  # admin 등록은 저장 위치 뒤에 가능하다
    assert flags(directory_and_storage) == (False, False, True)
    assert flags(done) == (False, False, False)
    assert empty.directory_configured is False
    assert directory_only.directory_configured is True


async def test_auth_status_does_not_ask_for_directory_setup_when_admin_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """마이그레이션이 AD 설정을 지워도 admin이 있으면 최초 설정은 다시 열리지 않는다(AC11)."""
    await seed_user(uow_factory, "boss", Role.ADMIN)

    status = await auth.status.execute()

    assert status.directory_configured is False
    assert status.needs_directory_setup is False
    assert status.needs_storage_setup is False
    assert status.needs_admin_setup is False


async def test_auth_status_ignores_deleted_and_non_admin_users(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)
    await seed_user(uow_factory, "gone", Role.ADMIN, deleted=True)
    await seed_user(uow_factory, "kim", Role.SALES)

    status = await auth.status.execute()

    assert status.needs_admin_setup is True


async def test_auth_status_asks_for_directory_setup_with_only_non_admin_users(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "kim", Role.SALES)
    await seed_user(uow_factory, "quit", Role.ADMIN, resigned=True)

    status = await auth.status.execute()

    assert status.needs_directory_setup is True


async def test_setup_directory_discovers_base_dn_and_saves_sealed_password(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    settings = make_directory_settings()

    stored = await auth.register_directory.execute(settings)

    assert (stored.revision, stored.updated_by) == (1, None)
    assert stored.connection == settings.connection
    assert stored.base_dn == BASE_DN
    assert auth.cipher.unseal(stored.sealed_bind_password) == BIND_PASSWORD
    assert BIND_PASSWORD not in stored.sealed_bind_password.token  # 평문이 아니라 암호문
    assert await _stored(uow_factory) == stored


async def test_setup_directory_checks_the_service_account_only(auth: AuthStack) -> None:
    settings = make_directory_settings()

    await auth.register_directory.execute(settings)

    assert auth.directory.discover_calls == [settings]
    assert auth.directory.authenticate_calls == []  # 관리자 검색·바인드 단계는 없다


async def test_setup_directory_stores_the_base_dn_the_directory_reported(
    auth: AuthStack,
) -> None:
    auth.directory.base_dn = "dc=found,dc=test"

    stored = await auth.register_directory.execute(make_directory_settings())

    assert stored.base_dn == "dc=found,dc=test"


async def test_setup_directory_can_be_overwritten_until_admin_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await auth.register_directory.execute(make_directory_settings())
    changed = make_directory_settings(host="dc2.corp.test", bind_password="Other-pw-3!")  # noqa: S106 - 가짜 값

    stored = await auth.register_directory.execute(changed)

    assert stored.revision == 2
    current = await _stored(uow_factory)
    assert current is not None
    assert current.connection.host == "dc2.corp.test"
    assert auth.cipher.unseal(current.sealed_bind_password) == "Other-pw-3!"


@pytest.mark.parametrize(
    "error",
    [
        DirectoryUnavailableError(LEAK, stage=VerificationStage.CONNECT),
        DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS),
        DirectoryMisconfiguredError(LEAK, stage=VerificationStage.SERVICE_BIND),
        DirectoryMisconfiguredError(LEAK, stage=VerificationStage.BASE_DN),
    ],
    ids=["connect", "tls", "service_bind", "base_dn"],
)
async def test_setup_directory_failure_at_each_stage_saves_nothing(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, error: DirectoryUnavailableError
) -> None:
    auth.directory.discover_fails_with = error

    with pytest.raises(DirectoryVerificationError) as caught:
        await auth.register_directory.execute(make_directory_settings())

    assert caught.value.stage is error.stage
    assert str(caught.value)
    assert LEAK not in str(caught.value)
    assert await _stored(uow_factory) is None


async def test_setup_directory_failure_without_a_stage_is_reported_as_connect(
    auth: AuthStack,
) -> None:
    auth.directory.discover_fails_with = DirectoryUnavailableError(LEAK)

    with pytest.raises(DirectoryVerificationError) as caught:
        await auth.register_directory.execute(make_directory_settings())

    assert caught.value.stage is VerificationStage.CONNECT


async def test_setup_directory_failure_keeps_the_previous_settings(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    first = await auth.register_directory.execute(make_directory_settings())
    auth.directory.discover_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    with pytest.raises(DirectoryVerificationError):
        await auth.register_directory.execute(make_directory_settings(host="dc9.corp.test"))

    assert await _stored(uow_factory) == first


async def test_setup_directory_is_closed_once_admin_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with pytest.raises(InvalidStateError) as caught:
        await auth.register_directory.execute(make_directory_settings(host="dc9.corp.test"))

    assert str(caught.value) == SETUP_CLOSED
    assert auth.directory.discover_calls == []
    assert await _stored(uow_factory) == stored


async def test_setup_directory_stays_closed_when_admin_exists_even_without_settings(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """마이그레이션이 설정 행을 지운 뒤에도 admin이 있으면 아무나 등록할 수 없다(AC11)."""
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with pytest.raises(InvalidStateError) as caught:
        await auth.register_directory.execute(make_directory_settings())

    assert str(caught.value) == SETUP_CLOSED
    assert auth.directory.discover_calls == []
    assert await _stored(uow_factory) is None
