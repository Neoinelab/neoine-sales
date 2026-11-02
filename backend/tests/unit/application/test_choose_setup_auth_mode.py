"""최초 설정 1단계 ChooseSetupAuthMode와 RegisterSetupDirectory의 방식 기록 (AC-1·2·3)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import AUTH_MODE_FIRST, DIRECTORY_FIRST, SETUP_CLOSED
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW, later
from tests.factories_directory import make_directory_settings
from tests.support.auth_seed import seed_auth_mode, seed_directory, seed_storage, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.storage_stack import StorageStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

STORAGE_PATH = "/data/neoine-sales/files"


async def _mode(uow_factory: UnitOfWorkFactory) -> AuthMode | None:
    async with uow_factory() as uow:
        stored = await uow.auth_settings.get()
    return None if stored is None else stored.mode


def test_the_new_messages_are_the_fixed_sentences() -> None:
    assert AUTH_MODE_FIRST == "먼저 인증 방식을 고르세요."


async def test_choose_auth_mode_saves_local(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    saved = await auth.choose_mode.execute(AuthMode.LOCAL)

    assert (saved.mode, saved.updated_at) == (AuthMode.LOCAL, NOW)
    assert await _mode(uow_factory) is AuthMode.LOCAL
    assert uow.commits == 1


async def test_choose_auth_mode_overwrites_before_admin(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    await auth.choose_mode.execute(AuthMode.LOCAL)
    clock.advance(60)

    saved = await auth.choose_mode.execute(AuthMode.AD)

    assert (saved.mode, saved.updated_at) == (AuthMode.AD, later(60))
    assert await _mode(uow_factory) is AuthMode.AD


@pytest.mark.parametrize("mode", list(AuthMode))
async def test_choose_auth_mode_after_admin_is_setup_closed(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, mode: AuthMode
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    uow.commits = 0

    with pytest.raises(InvalidStateError) as caught:
        await auth.choose_mode.execute(mode)

    assert str(caught.value) == SETUP_CLOSED
    assert await _mode(uow_factory) is AuthMode.AD
    assert uow.commits == 0


async def test_choose_auth_mode_after_a_resigned_admin_only_is_still_open(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "quit", Role.ADMIN, resigned=True)

    await auth.choose_mode.execute(AuthMode.LOCAL)

    assert await _mode(uow_factory) is AuthMode.LOCAL


async def test_choose_local_keeps_a_saved_directory_row(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)

    await auth.choose_mode.execute(AuthMode.LOCAL)

    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == stored


async def test_setup_directory_records_ad_mode(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await auth.register_directory.execute(make_directory_settings())

    assert await _mode(uow_factory) is AuthMode.AD


async def test_setup_directory_after_choosing_local_switches_to_ad(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await auth.choose_mode.execute(AuthMode.LOCAL)

    await auth.register_directory.execute(make_directory_settings())

    assert await _mode(uow_factory) is AuthMode.AD


async def test_failed_setup_directory_does_not_record_a_mode(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    from app.application.directory.errors import DirectoryVerificationError  # noqa: PLC0415
    from app.application.ports.directory import DirectoryUnavailableError  # noqa: PLC0415

    auth.directory.discover_fails_with = DirectoryUnavailableError("down")

    with pytest.raises(DirectoryVerificationError):
        await auth.register_directory.execute(make_directory_settings())

    assert await _mode(uow_factory) is None


# ---- 2단계(저장 위치)의 선행 조건 (AC-2) ----


async def test_setup_storage_without_mode_is_auth_mode_first(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute(STORAGE_PATH)

    assert str(caught.value) == AUTH_MODE_FIRST
    async with uow_factory() as uow:
        assert await uow.storage_settings.get() is None


async def test_setup_storage_local_mode_needs_no_directory(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    stored = await storage.register_setup.execute(STORAGE_PATH)

    assert stored.path.value == STORAGE_PATH


async def test_setup_storage_ad_mode_without_directory_is_directory_first(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)

    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute(STORAGE_PATH)

    assert str(caught.value) == DIRECTORY_FIRST


async def test_setup_storage_with_a_saved_directory_and_no_mode_row_still_works(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    stored = await storage.register_setup.execute(STORAGE_PATH)

    assert stored.path.value == STORAGE_PATH


async def test_setup_storage_local_mode_after_admin_is_setup_closed(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute(STORAGE_PATH)

    assert str(caught.value) == SETUP_CLOSED


async def test_setup_storage_keeps_working_for_a_later_overwrite_in_local_mode(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory, "/data/first")

    stored = await storage.register_setup.execute("/data/second")

    assert stored.path.value == "/data/second"
