"""사용자 관리·AD 설정 관리 유스케이스 조립 도우미(S5·S6). 단위 테스트와 FakeUseCases가 공용한다.

여기서 고정하는 생성자 계약(구현자가 따른다). 모든 `execute`는 키워드 인자로 호출한다.
- ListUsers(uow_factory)                                    app.application.user.list_users
  execute(*, status=UserStatusFilter.ACTIVE, offset=0, limit=DEFAULT_LIMIT) -> Sequence[User]
- ListUserOptions(uow_factory)                              ...user.list_user_options
  execute(*, keyword=None, include_resigned=False, role=None) -> Sequence[UserRef]
- ResolveUserRefs(uow_factory)                              ...user.resolve_user_refs
  execute(user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]  (퇴사자 포함)
- DeleteUser.execute(*, user_id, actor, reason=UserDeleteReason.RESIGNED) -> DeleteOutcome
- RegisterUser(uow_factory, clock)                          ...user.register_user
- DeleteUser(uow_factory, clock)                            ...user.delete_user
- GetDirectorySettings(uow_factory, cipher)                 app.application.directory.get_settings
  execute() -> DirectorySettingsView(.stored, .credential_readable)
- VerifyDirectorySettings(deps, *, allow_dev_sessions)      ...directory.verify_settings
  execute(*, actor, settings: DirectorySettings, password, client_ip) -> str (찾은 base_dn)
- TestDirectorySettings(uow_factory, cipher, verify)        ...directory.test_settings
  execute(*, actor, draft: DirectorySettingsDraft, password, client_ip) -> TestResult(base_dn 포함)
- UpdateDirectorySettings(uow_factory, clock, cipher, verify)  ...directory.update_settings
  execute(*, actor, draft: DirectorySettingsDraft, expected_revision: int | None, password,
  client_ip) -> StoredDirectorySettings

설정 유스케이스 4개는 새 Port(SecretCipher)가 필요해 처음 쓸 때 만든다. 사용자 관리만 쓰는 테스트가
AD 개편 구현에 묶이지 않는다.
"""

from functools import cached_property
from typing import TYPE_CHECKING

from app.application.user.delete_user import DeleteUser
from app.application.user.list_user_options import ListUserOptions
from app.application.user.list_users import ListUsers
from app.application.user.register_user import RegisterUser
from app.application.user.resolve_user_refs import ResolveUserRefs
from app.domain.auth.principal import Principal, Role
from tests.factories_auth import ADMIN_LOGIN, ADMIN_PASSWORD
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.application.directory.get_settings import GetDirectorySettings
    from app.application.directory.test_settings import TestDirectorySettings
    from app.application.directory.update_settings import UpdateDirectorySettings
    from app.application.directory.verify_settings import VerifyDirectorySettings
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

ADMIN_ACTOR = Principal(uid(ADMIN_LOGIN), ADMIN_LOGIN, "root@corp.test", "루트 관리자", Role.ADMIN)
# dev-login admin. 이제 users 행이 있는 일반 사용자지만 AD 검증은 우회한다(예약 아이디)
DEV_ACTOR = Principal(uid("dev-admin"), "dev-admin", None, "dev admin", Role.ADMIN)


class AdminStack:
    """사용자 관리·AD 설정 관리 유스케이스 묶음(설정 유스케이스는 처음 쓸 때 만든다)."""

    def __init__(
        self,
        auth: AuthStack,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        *,
        allow_dev_sessions: bool,
    ) -> None:
        self._auth = auth
        self._uow_factory = uow_factory
        self._clock = clock
        self._allow_dev_sessions = allow_dev_sessions
        self.list_users = ListUsers(uow_factory)
        self.register_user = RegisterUser(uow_factory, clock)
        self.delete_user = DeleteUser(uow_factory, clock)
        self.list_user_options = ListUserOptions(uow_factory)
        self.resolve_user_refs = ResolveUserRefs(uow_factory)

    @cached_property
    def get_settings(self) -> GetDirectorySettings:
        from app.application.directory.get_settings import GetDirectorySettings  # noqa: PLC0415

        return GetDirectorySettings(self._uow_factory, self._auth.cipher)

    @cached_property
    def verify(self) -> VerifyDirectorySettings:
        from app.application.directory.verify_settings import (  # noqa: PLC0415
            VerifyDirectorySettings,
        )

        return VerifyDirectorySettings(self._auth.deps, allow_dev_sessions=self._allow_dev_sessions)

    @cached_property
    def test_settings(self) -> TestDirectorySettings:
        from app.application.directory.test_settings import (  # noqa: PLC0415
            TestDirectorySettings,
        )

        return TestDirectorySettings(self._uow_factory, self._auth.cipher, self.verify)

    @cached_property
    def update_settings(self) -> UpdateDirectorySettings:
        from app.application.directory.update_settings import (  # noqa: PLC0415
            UpdateDirectorySettings,
        )

        return UpdateDirectorySettings(
            self._uow_factory, self._clock, self._auth.cipher, self.verify
        )


def build_admin_stack(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    *,
    allow_dev_sessions: bool = True,
) -> AdminStack:
    return AdminStack(auth, uow_factory, clock, allow_dev_sessions=allow_dev_sessions)
