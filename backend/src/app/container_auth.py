"""인증 유스케이스 조립(Composition Root의 일부). 로그인 시도 제한·세션 발급을 한 곳에서 묶는다."""

from datetime import timedelta
from typing import TYPE_CHECKING

from app.application.auth.auth_status import GetAuthStatus
from app.application.auth.authenticate import Authenticate
from app.application.auth.deps import AuthDeps
from app.application.auth.dev_login import DevLogin
from app.application.auth.directory_login import DirectoryLogin
from app.application.auth.issue_session import IssueSession
from app.application.auth.logout import Logout
from app.application.auth.setup_directory import RegisterSetupDirectory
from app.application.auth.setup_first_admin import SetupFirstAdmin
from app.application.auth.throttle import LoginThrottle
from app.domain.auth.login_failure import FailurePolicy

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.directory import DirectoryAuthenticator
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.config.base import Settings


class AuthAssembly:
    """설정과 Port 구현체로 인증 유스케이스를 만든다."""

    def __init__(
        self,
        settings: Settings,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        directory: DirectoryAuthenticator,
    ) -> None:
        window = timedelta(minutes=settings.login_failure_window_minutes)
        lock = timedelta(minutes=settings.login_lock_minutes)
        throttle = LoginThrottle(
            uow_factory,
            clock,
            secret=settings.jwt_secret.get_secret_value(),
            account_policy=FailurePolicy(settings.login_max_failures_per_account, window, lock),
            ip_policy=FailurePolicy(settings.login_max_failures_per_ip, window, lock),
        )
        self._uow_factory = uow_factory
        self._clock = clock
        self._directory = directory
        self._deps = AuthDeps(uow_factory, clock, directory, throttle)
        self._issue_session = IssueSession(
            uow_factory, clock, timedelta(hours=settings.session_ttl_hours)
        )
        self._allow_dev_sessions = settings.dev_login_enabled

    @property
    def deps(self) -> AuthDeps:
        return self._deps

    @property
    def allow_dev_sessions(self) -> bool:
        return self._allow_dev_sessions

    def auth_status(self) -> GetAuthStatus:
        return GetAuthStatus(self._uow_factory)

    def register_setup_directory(self) -> RegisterSetupDirectory:
        return RegisterSetupDirectory(self._uow_factory, self._clock, self._directory)

    def setup_first_admin(self) -> SetupFirstAdmin:
        return SetupFirstAdmin(self._deps, self._issue_session)

    def directory_login(self) -> DirectoryLogin:
        return DirectoryLogin(self._deps, self._issue_session)

    def dev_login(self) -> DevLogin:
        return DevLogin(self._issue_session)

    def authenticate(self) -> Authenticate:
        return Authenticate(
            self._uow_factory, self._clock, allow_dev_sessions=self._allow_dev_sessions
        )

    def logout(self) -> Logout:
        return Logout(self._uow_factory, self._clock)
