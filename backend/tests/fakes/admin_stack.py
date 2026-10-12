"""사용자 관리·AD 설정 관리 유스케이스 조립 도우미(S5·S6). 단위 테스트와 FakeUseCases가 공용한다.

여기서 고정하는 생성자 계약(구현자가 따른다). 모든 `execute`는 키워드 인자로 호출한다.
- ListUsers(uow_factory)                                    app.application.user.list_users
- RegisterUser(uow_factory, clock)                          ...user.register_user
- DeleteUser(uow_factory, clock)                            ...user.delete_user
- GetDirectorySettings(uow_factory)                         app.application.directory.get_settings
- VerifyDirectorySettings(deps, *, allow_dev_sessions)      ...directory.verify_settings
- TestDirectorySettings(verify)                             ...directory.test_settings
- UpdateDirectorySettings(uow_factory, clock, verify)       ...directory.update_settings
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.directory.get_settings import GetDirectorySettings
from app.application.directory.test_settings import TestDirectorySettings as TestSettingsUseCase
from app.application.directory.update_settings import UpdateDirectorySettings
from app.application.directory.verify_settings import VerifyDirectorySettings
from app.application.user.delete_user import DeleteUser
from app.application.user.list_users import ListUsers
from app.application.user.register_user import RegisterUser

from app.domain.auth.principal import Principal, Role
from tests.factories_auth import ADMIN_LOGIN, ADMIN_PASSWORD

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack

__all__ = [
    "ADMIN_ACTOR",
    "ADMIN_LOGIN",
    "ADMIN_PASSWORD",
    "DEV_ACTOR",
    "AdminStack",
    "build_admin_stack",
]

ADMIN_ACTOR = Principal(ADMIN_LOGIN, "root@corp.test", "루트 관리자", Role.ADMIN)
DEV_ACTOR = Principal("dev:admin", None, "dev admin", Role.ADMIN)  # users 행이 없는 dev-login admin


@dataclass(frozen=True, slots=True)
class AdminStack:
    list_users: ListUsers
    register_user: RegisterUser
    delete_user: DeleteUser
    get_settings: GetDirectorySettings
    verify: VerifyDirectorySettings
    test_settings: TestSettingsUseCase
    update_settings: UpdateDirectorySettings


def build_admin_stack(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    *,
    allow_dev_sessions: bool = True,
) -> AdminStack:
    verify = VerifyDirectorySettings(auth.deps, allow_dev_sessions=allow_dev_sessions)
    return AdminStack(
        list_users=ListUsers(uow_factory),
        register_user=RegisterUser(uow_factory, clock),
        delete_user=DeleteUser(uow_factory, clock),
        get_settings=GetDirectorySettings(uow_factory),
        verify=verify,
        test_settings=TestSettingsUseCase(verify),
        update_settings=UpdateDirectorySettings(uow_factory, clock, verify),
    )
