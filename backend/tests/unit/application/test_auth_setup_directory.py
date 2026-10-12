"""최초 설정 1단계 RegisterSetupDirectory와 GetAuthStatus (SETUP-1~4, T-U16·U19~U22)."""

from typing import TYPE_CHECKING

import pytest
from app.application.auth.messages import SETUP_CLOSED
from app.application.directory.errors import DirectoryVerificationError

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories_auth import make_directory_settings
from tests.support.auth_seed import seed_directory, seed_user

if TYPE_CHECKING:
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
    empty = await auth.status.execute()
    await seed_directory(uow_factory)
    directory_only = await auth.status.execute()
    await seed_user(uow_factory, "boss", Role.ADMIN)
    done = await auth.status.execute()

    assert (empty.directory_configured, empty.needs_directory_setup, empty.needs_admin_setup) == (
        False,
        True,
        False,
    )
    assert (
        directory_only.directory_configured,
        directory_only.needs_directory_setup,
        directory_only.needs_admin_setup,
    ) == (True, False, True)
    assert (done.directory_configured, done.needs_directory_setup, done.needs_admin_setup) == (
        True,
        False,
        False,
    )


async def test_auth_status_ignores_deleted_and_non_admin_users(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "gone", Role.ADMIN, deleted=True)
    await seed_user(uow_factory, "kim", Role.SALES)

    status = await auth.status.execute()

    assert status.needs_admin_setup is True


async def test_register_setup_directory_probes_then_saves(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    settings = make_directory_settings()

    stored = await auth.register_directory.execute(settings)

    assert (stored.revision, stored.updated_by, stored.settings) == (1, None, settings)
    assert auth.directory.probe_calls == [settings]
    assert uow.users.roster_locks >= 1
    assert await _stored(uow_factory) == stored


async def test_setup_directory_can_be_overwritten_until_admin_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await auth.register_directory.execute(make_directory_settings())
    changed = make_directory_settings(base_dn="dc=other,dc=test")

    stored = await auth.register_directory.execute(changed)

    assert stored.revision == 2
    current = await _stored(uow_factory)
    assert current is not None
    assert current.settings == changed


@pytest.mark.parametrize("stage", [VerificationStage.CONNECT, VerificationStage.TLS])
async def test_setup_directory_probe_failure_saves_nothing(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, stage: VerificationStage
) -> None:
    auth.directory.probe_fails_with = DirectoryUnavailableError(LEAK, stage=stage)

    with pytest.raises(DirectoryVerificationError) as caught:
        await auth.register_directory.execute(make_directory_settings())

    assert caught.value.stage is stage
    assert str(caught.value)
    assert LEAK not in str(caught.value)
    assert await _stored(uow_factory) is None


async def test_setup_directory_probe_failure_keeps_the_previous_settings(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    first = await auth.register_directory.execute(make_directory_settings())
    auth.directory.probe_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    with pytest.raises(DirectoryVerificationError):
        await auth.register_directory.execute(make_directory_settings(base_dn="dc=x,dc=test"))

    assert await _stored(uow_factory) == first


async def test_setup_directory_is_closed_once_admin_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with pytest.raises(InvalidStateError) as caught:
        await auth.register_directory.execute(make_directory_settings(base_dn="dc=x,dc=test"))

    assert str(caught.value) == SETUP_CLOSED
    assert auth.directory.probe_calls == []
    assert await _stored(uow_factory) == stored


async def test_setup_directory_rechecks_admin_after_the_probe(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """probe 도중 다른 요청이 admin을 만들면, 잠금 뒤 재확인에서 막히고 저장하지 않는다."""

    async def admin_registers_meanwhile() -> None:
        await seed_user(uow_factory, "boss", Role.ADMIN)

    auth.directory.on_probe = admin_registers_meanwhile

    with pytest.raises(InvalidStateError) as caught:
        await auth.register_directory.execute(make_directory_settings())

    assert str(caught.value) == SETUP_CLOSED
    assert await _stored(uow_factory) is None
