"""GetAuthStatus의 인증 방식(auth_mode)과 단계 플래그 (AC-1·AC-14).

needs_directory_setup = admin 없음 and (방식 미선택 or (ad and AD 설정 없음))
needs_storage_setup   = admin 없음 and 저장 위치 없음
needs_admin_setup     = admin 없음 and 저장 위치 있음 and (local or (ad and AD 설정 있음))
방식 행이 없을 때: admin이나 AD 설정이 이미 있으면 ad로 본다(방식이 생기기 전에 설정한 시스템).
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.support.auth_seed import seed_auth_mode, seed_directory, seed_storage, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack


async def _flags(auth: AuthStack) -> tuple[bool, bool, bool]:
    status = await auth.status.execute()
    return (status.needs_directory_setup, status.needs_storage_setup, status.needs_admin_setup)


async def test_auth_status_without_mode_needs_directory_step(auth: AuthStack) -> None:
    status = await auth.status.execute()

    assert status.auth_mode is None
    assert await _flags(auth) == (True, True, False)


async def test_auth_status_local_mode_skips_directory_step(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    status = await auth.status.execute()

    assert status.auth_mode is AuthMode.LOCAL
    assert await _flags(auth) == (False, True, False)


async def test_auth_status_local_mode_with_storage_needs_admin(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory)

    assert await _flags(auth) == (False, False, True)


async def test_auth_status_local_mode_needs_no_directory_even_though_none_is_saved(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory)

    status = await auth.status.execute()

    assert status.directory_configured is False
    assert status.needs_directory_setup is False


async def test_auth_status_ad_mode_without_directory_needs_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_storage(uow_factory)

    status = await auth.status.execute()

    assert status.auth_mode is AuthMode.AD
    assert await _flags(auth) == (True, False, False)


async def test_auth_status_ad_mode_with_directory_and_storage_needs_admin(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)

    assert await _flags(auth) == (False, False, True)


@pytest.mark.parametrize("mode", list(AuthMode))
async def test_auth_status_closes_every_step_once_an_admin_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, mode: AuthMode
) -> None:
    await seed_auth_mode(uow_factory, mode)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    status = await auth.status.execute()

    assert status.auth_mode is mode
    assert await _flags(auth) == (False, False, False)


async def test_auth_status_without_mode_row_but_with_admin_reports_ad(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN)

    status = await auth.status.execute()

    assert status.auth_mode is AuthMode.AD


async def test_auth_status_without_mode_row_but_with_directory_reports_ad(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)

    status = await auth.status.execute()

    assert status.auth_mode is AuthMode.AD
    assert await _flags(auth) == (False, False, True)


async def test_auth_status_stored_local_mode_beats_a_leftover_directory_row(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    status = await auth.status.execute()

    assert status.auth_mode is AuthMode.LOCAL
    assert status.directory_configured is True
