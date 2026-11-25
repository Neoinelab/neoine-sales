"""최초 설정 진행 상태(GetAuthStatus)의 의미: SU-001~SU-006.

플래그 판정의 전체 조합(BDD 밖)은 `test_auth_status_storage.py`·
`test_auth_status_modes.py`가 맡는다.
"""

from typing import TYPE_CHECKING

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.support.auth_seed import (
    seed_auth_mode,
    seed_directory,
    seed_storage,
    seed_user,
)

if TYPE_CHECKING:
    from app.application.auth.auth_status import AuthStatus
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.storage_stack import StorageStack


def _flags(status: AuthStatus) -> tuple[bool, bool, bool]:
    return (status.needs_directory_setup, status.needs_storage_setup, status.needs_admin_setup)


async def test_new_system_has_no_mode_and_needs_directory_and_storage(auth: AuthStack) -> None:
    """새 시스템은 방식 미선택이고 AD·저장 위치 단계가 필요하며 관리자 단계는 아직이다.

    테스트 코드: SU-001
    """
    # when: 진행 상태를 조회한다 (전제: 사용자·방식·AD 설정·저장 위치가 하나도 없다)
    status = await auth.status.execute()

    # then: auth_mode None, (directory, storage, admin) = (True, True, False)
    assert status.auth_mode is None
    assert _flags(status) == (True, True, False)


async def test_choosing_local_drops_the_directory_step_and_storage_leaves_only_admin(
    auth: AuthStack, storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local을 고르면 AD 단계가 없어지고 저장 위치를 저장하면 관리자 단계만 남는다.

    테스트 코드: SU-002
    """
    # given: 새 시스템에서 방식 local을 골랐다(AD 설정은 없다)
    await auth.choose_mode.execute(AuthMode.LOCAL)

    # when: 진행 상태를 조회하고, 저장 위치 /data/files를 저장한 뒤 다시 조회한다
    before = await auth.status.execute()
    await storage.register_setup.execute("/data/files")
    after = await auth.status.execute()

    # then: 처음은 local·(False, True, False), 다음은 (False, False, True)
    assert before.auth_mode is AuthMode.LOCAL
    assert _flags(before) == (False, True, False)
    assert _flags(after) == (False, False, True)


async def test_ad_mode_needs_directory_until_directory_and_storage_exist(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """ad 방식에서 AD 설정이 없으면 AD 단계가, AD·저장 위치가 있으면 관리자 단계만 남는다.

    테스트 코드: SU-003
    """
    # given: 방식 ad가 저장되어 있고 AD 설정이 없다
    await seed_auth_mode(uow_factory, AuthMode.AD)

    # when: 진행 상태를 조회하고, AD 설정과 저장 위치를 저장한 뒤 다시 조회한다
    before = await auth.status.execute()
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)
    after = await auth.status.execute()

    # then: 처음은 directory 필요·admin 아직, 다음은 admin 단계만 남는다
    assert (before.needs_directory_setup, before.needs_admin_setup) == (True, False)
    assert _flags(after) == (False, False, True)


async def test_missing_auth_settings_reopens_setup_even_with_an_admin(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """인증 방식 행이 없으면 기존 관리자와 관계없이 다시 설정한다.

    테스트 코드: SU-004
    """
    # given: 재직 admin이 있고 AD 설정·저장 위치 행이 없다
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: 진행 상태를 조회한다
    status = await auth.status.execute()

    # then: 셋 다 False, auth_mode는 ad, AD 설정은 없으므로 directory_configured도 False
    assert _flags(status) == (True, True, False)
    assert status.auth_mode is None
    assert status.directory_configured is False


async def test_resigned_admin_or_non_admins_leave_the_setup_open(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사한 admin이나 admin이 아닌 사용자만 있으면 설정은 열려 있다.

    테스트 코드: SU-005
    """
    # given: 퇴사 처리된 admin 1명과 재직 sales·user만 있고 설정 행이 없다
    await seed_user(uow_factory, "quit", Role.ADMIN, resigned=True)
    await seed_user(uow_factory, "kim", Role.SALES)
    await seed_user(uow_factory, "lee", Role.USER)

    # when: 진행 상태를 조회하고 인증 방식 local을 고른다
    status = await auth.status.execute()
    saved = await auth.choose_mode.execute(AuthMode.LOCAL)

    # then: 디렉터리·저장 위치 단계가 필요하고 방식 선택은 성공한다
    assert (status.needs_directory_setup, status.needs_storage_setup) == (True, True)
    assert saved.mode is AuthMode.LOCAL


async def test_an_admin_without_auth_settings_has_no_chosen_mode(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """방식 행이 없으면 재직 관리자만 있어도 미선택이다.

    테스트 코드: SU-006
    """
    # given: 방식 행 없이 재직 admin만 있다
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: 진행 상태를 조회한다
    status = await auth.status.execute()

    # then: auth_mode는 ad
    assert status.auth_mode is None


async def test_a_directory_without_auth_settings_still_needs_a_mode(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """방식 행·admin 없이 AD 설정 행만 있으면 ad이고 AD 단계는 끝난 것으로 본다.

    테스트 코드: SU-006
    """
    # given: 방식 행·admin 없이 AD 설정 행만 있다
    await seed_directory(uow_factory)

    # when: 진행 상태를 조회한다
    status = await auth.status.execute()

    # then: auth_mode는 ad, needs_directory_setup은 False
    assert status.auth_mode is None
    assert status.needs_directory_setup is True


async def test_stored_local_beats_a_leftover_directory_row(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장된 local은 남아 있는 AD 설정 행보다 우선한다.

    테스트 코드: SU-006
    """
    # given: 방식 local이 저장되어 있고 AD 설정 행도 남아 있다
    await seed_directory(uow_factory)
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    # when: 진행 상태를 조회한다
    status = await auth.status.execute()

    # then: auth_mode는 local
    assert status.auth_mode is AuthMode.LOCAL
