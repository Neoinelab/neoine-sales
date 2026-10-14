"""사용자 관리·AD 설정 관리 유스케이스 조립(Composition Root의 일부)."""

from typing import TYPE_CHECKING

from app.application.directory.get_settings import GetDirectorySettings
from app.application.directory.test_settings import TestDirectorySettings
from app.application.directory.update_settings import UpdateDirectorySettings
from app.application.directory.verify_settings import VerifyDirectorySettings
from app.application.user.delete_user import DeleteUser
from app.application.user.list_user_options import ListUserOptions
from app.application.user.list_users import ListUsers
from app.application.user.register_user import RegisterUser
from app.application.user.resolve_user_refs import ResolveUserRefs

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class AdminAssembly:
    """AD 설정 검증을 공유하는 관리 유스케이스를 만든다."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        auth_deps: AuthDeps,
        *,
        allow_dev_sessions: bool,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._verify = VerifyDirectorySettings(auth_deps, allow_dev_sessions=allow_dev_sessions)

    def list_users(self) -> ListUsers:
        return ListUsers(self._uow_factory)

    def register_user(self) -> RegisterUser:
        return RegisterUser(self._uow_factory, self._clock)

    def delete_user(self) -> DeleteUser:
        return DeleteUser(self._uow_factory, self._clock)

    def list_user_options(self) -> ListUserOptions:
        return ListUserOptions(self._uow_factory)

    def resolve_user_refs(self) -> ResolveUserRefs:
        return ResolveUserRefs(self._uow_factory)

    def get_directory_settings(self) -> GetDirectorySettings:
        return GetDirectorySettings(self._uow_factory)

    def test_directory_settings(self) -> TestDirectorySettings:
        return TestDirectorySettings(self._verify)

    def update_directory_settings(self) -> UpdateDirectorySettings:
        return UpdateDirectorySettings(self._uow_factory, self._clock, self._verify)
