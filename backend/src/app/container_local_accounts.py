"""앱 자체 계정 관리(local 인증 모드) 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.account.change_my_password import ChangeMyPassword
from app.application.account.get_my_profile import GetMyProfile
from app.application.account.update_my_profile import UpdateMyProfile
from app.application.auth.issue_session import IssueSession
from app.application.auth.password_login import PasswordLogin
from app.application.auth.setup_admin import SetupAdmin
from app.application.auth.setup_auth_mode import ChooseSetupAuthMode
from app.application.user.reset_user_password import ResetUserPassword
from app.application.user.update_user_profile import UpdateUserProfile

if TYPE_CHECKING:
    from datetime import timedelta

    from app.application.auth.deps import AuthDeps
    from app.application.ports.clock import Clock
    from app.application.ports.password_hasher import PasswordHasher
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class LocalAccountUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock
    _auth_deps: AuthDeps
    _session_ttl: timedelta
    password_hasher: PasswordHasher

    def _issue_session(self) -> IssueSession:
        return IssueSession(self._uow, self._clock, self._session_ttl)

    def choose_setup_auth_mode(self) -> ChooseSetupAuthMode:
        return ChooseSetupAuthMode(self._uow, self._clock)

    def setup_admin(self) -> SetupAdmin:
        return SetupAdmin(self._auth_deps, self._issue_session())

    def password_login(self) -> PasswordLogin:
        return PasswordLogin(self._auth_deps, self._issue_session())

    def reset_user_password(self) -> ResetUserPassword:
        return ResetUserPassword(self._uow, self._clock, self.password_hasher)

    def update_user_profile(self) -> UpdateUserProfile:
        return UpdateUserProfile(self._uow, self._clock)

    def get_my_profile(self) -> GetMyProfile:
        return GetMyProfile(self._uow)

    def update_my_profile(self) -> UpdateMyProfile:
        return UpdateMyProfile(self._uow, self._clock)

    def change_my_password(self) -> ChangeMyPassword:
        return ChangeMyPassword(self._auth_deps)
