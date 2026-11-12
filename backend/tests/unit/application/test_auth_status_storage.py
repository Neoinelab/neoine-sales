"""GetAuthStatus의 저장 위치 단계 플래그: AD, 저장 위치, admin 세 조건의 모든 조합."""

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
    # admin이 있으면 AD 설정이 없어도 최초 설정 1단계는 열리지 않는다(AC11)
    # admin이 있으면 저장 위치 단계는 더 이상 열려 있지 않다(저장 위치가 없는 옛 DB도 마찬가지)
    ((False, False, True), (False, False, False)),
    ((True, False, True), (False, False, False)),
    ((False, True, True), (False, False, False)),
    ((True, True, True), (False, False, False)),
]


@pytest.mark.parametrize(("conditions", "expected"), CASES)
async def test_auth_status_flags_follow_the_three_setup_conditions(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    conditions: tuple[bool, bool, bool],
    expected: tuple[bool, bool, bool],
) -> None:
    """AD 설정·저장 위치·admin 세 조건의 모든 조합이 단계 플래그를 정한다.

    테스트 코드: AU-063
    """
    # given: AD 설정·저장 위치·admin 있음/없음의 조합
    """AD 설정·저장 위치·admin 세 조건의 모든 조합에서 단계 플래그가 규칙대로다."""
    # given: 조합에 따라 AD 설정·저장 위치·admin을 둔다
    directory, storage, admin = conditions
    if directory:
        await seed_directory(uow_factory)
    if storage:
        await seed_storage(uow_factory)
    if admin:
        await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: 인증 설정 상태를 조회하면
    status = await auth.status.execute()

    # then: 표의 단계 플래그와 같다
    assert (
        status.needs_directory_setup,
        status.needs_storage_setup,
        status.needs_admin_setup,
    ) == expected


async def test_auth_status_reports_whether_the_storage_is_configured(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장 위치 설정 여부가 상태에 나온다.

    테스트 코드: AU-063
    """
    # given: 저장 위치를 설정하기 전과 후
    before = await auth.status.execute()
    await seed_storage(uow_factory)
    # when: 상태를 조회하면
    after = await auth.status.execute()

    # then: false에서 true로 바뀐다
    assert (before.storage_configured, after.storage_configured) == (False, True)
