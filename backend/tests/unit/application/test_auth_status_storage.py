"""GetAuthStatus의 저장 위치 단계 플래그 (P2b AC-01): AD, 저장 위치, admin 세 조건의 모든 조합."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from tests.support.auth_seed import seed_directory, seed_storage, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack

# (AD 설정, 저장 위치, admin) -> (needs_directory_setup, needs_storage_setup, needs_admin_setup)
CASES = [
    ((False, False, False), (True, True, False)),
    ((True, False, False), (False, True, False)),
    ((False, True, False), (True, False, False)),
    ((True, True, False), (False, False, True)),
    # admin이 있으면 저장 위치 단계는 더 이상 열려 있지 않다(저장 위치가 없는 옛 DB도 마찬가지)
    ((False, False, True), (True, False, False)),
    ((True, False, True), (False, False, False)),
    ((False, True, True), (True, False, False)),
    ((True, True, True), (False, False, False)),
]


@pytest.mark.parametrize(("conditions", "expected"), CASES)
async def test_auth_status_flags_follow_the_three_setup_conditions(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    conditions: tuple[bool, bool, bool],
    expected: tuple[bool, bool, bool],
) -> None:
    directory, storage, admin = conditions
    if directory:
        await seed_directory(uow_factory)
    if storage:
        await seed_storage(uow_factory)
    if admin:
        await seed_user(uow_factory, "boss", Role.ADMIN)

    status = await auth.status.execute()

    assert (
        status.needs_directory_setup,
        status.needs_storage_setup,
        status.needs_admin_setup,
    ) == expected


async def test_auth_status_reports_whether_the_storage_is_configured(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    before = await auth.status.execute()
    await seed_storage(uow_factory)
    after = await auth.status.execute()

    assert (before.storage_configured, after.storage_configured) == (False, True)


async def test_resigned_admin_does_not_close_the_storage_step(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "gone", Role.ADMIN, resigned=True)

    status = await auth.status.execute()

    assert (status.needs_storage_setup, status.needs_admin_setup) == (True, False)
