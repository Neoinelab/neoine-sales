"""사용자 관리·AD 설정 관리 유스케이스 조립 도우미(S5·S6). 단위 테스트와 FakeUseCases가 공용한다.

여기서 고정하는 생성자 계약(구현자가 따른다). 모든 `execute`는 키워드 인자로 호출한다.
- ListUsers(uow_factory)                                    app.application.user.list_users
  execute(*, status=UserStatusFilter.ACTIVE, offset=0, limit=DEFAULT_LIMIT) -> Sequence[User]
- ListUserOptions(uow_factory)                              ...user.list_user_options
  execute(*, keyword=None, include_resigned=False, role=None) -> Sequence[UserRef]
- ResolveUserRefs(uow_factory)                              ...user.resolve_user_refs
  execute(user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]  (퇴사자 포함)
- DeleteUser.execute(*, user_id, actor) -> DeleteOutcome
- RegisterUser(uow_factory, clock, hasher)                  ...user.register_user
  execute(*, login_id, role, actor, display_name=None, email=None, phone=None,
  password: Password | None = None) -> User
  (모드 LOCAL: password·display_name 필수, AD: password 금지)
- ResetUserPassword(uow_factory, clock, hasher)             ...user.reset_user_password
  execute(*, user_id, password: Password, actor) -> None
- UpdateUserProfile(uow_factory, clock)                     ...user.update_user_profile
  execute(*, user_id, changes: ProfileChanges, actor) -> User
- GetMyProfile(uow_factory)                                 app.application.account.get_my_profile
  execute(actor) -> MyProfile(.user, .mode, .can_edit_name_email, .can_change_password)
- UpdateMyProfile(uow_factory, clock)                       ...account.update_my_profile
  execute(*, actor, changes: ProfileChanges) -> MyProfile
- DeleteUser(uow_factory, clock)                            ...user.delete_user
- GetDirectorySettings(uow_factory, cipher)                 app.application.directory.get_settings
  execute() -> DirectorySettingsView(.stored, .credential_readable)
- VerifyDirectorySettings(deps)                             ...directory.verify_settings
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

from app.application.directory.connection_proof import DirectoryConnectionProof
from app.application.user.delete_user import DeleteUser
from app.application.user.list_user_options import ListUserOptions
from app.application.user.list_users import ListUsers
from app.application.user.register_user import RegisterUser
from app.application.user.resolve_user_refs import ResolveUserRefs
from app.domain.auth.principal import Principal, Role
from tests.factories_auth import ADMIN_LOGIN, ADMIN_PASSWORD
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.application.account.get_my_profile import GetMyProfile
    from app.application.account.update_my_profile import UpdateMyProfile
    from app.application.directory.get_settings import GetDirectorySettings
    from app.application.directory.test_settings import TestDirectorySettings
    from app.application.directory.update_settings import UpdateDirectorySettings
    from app.application.directory.verify_settings import VerifyDirectorySettings
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.user.reset_user_password import ResetUserPassword
    from app.application.user.update_user_profile import UpdateUserProfile
    from tests.fakes.auth_stack import AuthStack

__all__ = [
    "ADMIN_ACTOR",
    "ADMIN_LOGIN",
    "ADMIN_PASSWORD",
    "OTHER_ADMIN_ACTOR",
    "AdminStack",
    "build_admin_stack",
]

ADMIN_ACTOR = Principal(uid(ADMIN_LOGIN), ADMIN_LOGIN, "root@corp.test", "루트 관리자", Role.ADMIN)
# 행위자가 둘 필요한 시나리오용 두 번째 관리자(AD 검증 예외 없음: 설정 저장·테스트는 비밀번호 필요)
OTHER_ADMIN_ACTOR = Principal(uid("other-admin"), "other-admin", None, "other admin", Role.ADMIN)


class AdminStack:
    """사용자 관리·AD 설정 관리 유스케이스 묶음(설정 유스케이스는 처음 쓸 때 만든다)."""

    def __init__(
        self,
        auth: AuthStack,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._auth = auth
        self._uow_factory = uow_factory
        self._clock = clock
        self.list_users = ListUsers(uow_factory)
        self.delete_user = DeleteUser(uow_factory, clock)
        self.list_user_options = ListUserOptions(uow_factory)
        self.resolve_user_refs = ResolveUserRefs(uow_factory)

    # 앱 자체 계정 관리 개편으로 생성자가 바뀐 유스케이스와 새 유스케이스는 처음 쓸 때 만든다
    @cached_property
    def register_user(self) -> RegisterUser:
        return RegisterUser(self._uow_factory, self._clock, self._auth.hasher)

    @cached_property
    def reset_password(self) -> ResetUserPassword:
        from app.application.user.reset_user_password import (  # noqa: PLC0415
            ResetUserPassword,
        )

        return ResetUserPassword(self._uow_factory, self._clock, self._auth.hasher)

    @cached_property
    def update_profile(self) -> UpdateUserProfile:
        from app.application.user.update_user_profile import (  # noqa: PLC0415
            UpdateUserProfile,
        )

        return UpdateUserProfile(self._uow_factory, self._clock)

    @cached_property
    def get_my_profile(self) -> GetMyProfile:
        from app.application.account.get_my_profile import GetMyProfile  # noqa: PLC0415

        return GetMyProfile(self._uow_factory)

    @cached_property
    def update_my_profile(self) -> UpdateMyProfile:
        from app.application.account.update_my_profile import UpdateMyProfile  # noqa: PLC0415

        return UpdateMyProfile(self._uow_factory, self._clock)

    @cached_property
    def get_settings(self) -> GetDirectorySettings:
        from app.application.directory.get_settings import GetDirectorySettings  # noqa: PLC0415

        return GetDirectorySettings(self._uow_factory)

    @cached_property
    def verify(self) -> VerifyDirectorySettings:
        from app.application.directory.verify_settings import (  # noqa: PLC0415
            VerifyDirectorySettings,
        )

        return VerifyDirectorySettings(
            self._auth.directory, DirectoryConnectionProof(self._auth.cipher, self._clock)
        )

    @cached_property
    def test_settings(self) -> TestDirectorySettings:
        from app.application.directory.test_settings import (  # noqa: PLC0415
            TestDirectorySettings,
        )

        return TestDirectorySettings(self._uow_factory, self.verify)

    @cached_property
    def update_settings(self) -> UpdateDirectorySettings:
        from app.application.directory.update_settings import (  # noqa: PLC0415
            UpdateDirectorySettings,
        )

        return UpdateDirectorySettings(
            self._uow_factory, self._clock, DirectoryConnectionProof(self._auth.cipher, self._clock)
        )


def build_admin_stack(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
) -> AdminStack:
    return AdminStack(auth, uow_factory, clock)
