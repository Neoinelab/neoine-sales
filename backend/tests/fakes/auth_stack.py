"""인증 유스케이스 조립 도우미. 단위 테스트와 FakeUseCases가 같은 방식으로 조립한다.

여기서 고정하는 생성자 계약(구현자가 따른다):
- AuthDeps(uow_factory, clock, directory, throttle)                  app.application.auth.deps
- LoginThrottle(uow_factory, clock, *, secret, account_policy, ip_policy)   ...auth.throttle
- DirectoryLogin(deps, issue_session), SetupFirstAdmin(deps, issue_session)
- RegisterSetupDirectory(uow_factory, clock, directory)
- GetAuthStatus(uow_factory), Authenticate(uow_factory, clock, *, allow_dev_sessions)
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from app.application.auth.auth_status import GetAuthStatus
from app.application.auth.deps import AuthDeps
from app.application.auth.directory_login import DirectoryLogin
from app.application.auth.setup_directory import RegisterSetupDirectory
from app.application.auth.setup_first_admin import SetupFirstAdmin
from app.application.auth.throttle import LoginThrottle

from app.application.auth.authenticate import Authenticate
from app.application.auth.dev_login import DevLogin
from app.application.auth.issue_session import IssueSession
from app.application.auth.logout import Logout
from tests.factories_auth import make_policy
from tests.fakes.directory import FakeDirectoryAuthenticator

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory

THROTTLE_SECRET = "t" * 40
SESSION_TTL = timedelta(hours=8)
MAX_PER_ACCOUNT = 5
MAX_PER_IP = 30
WINDOW = timedelta(minutes=15)
LOCK = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class AuthStack:
    directory: FakeDirectoryAuthenticator
    throttle: LoginThrottle
    deps: AuthDeps
    issue: IssueSession
    status: GetAuthStatus
    register_directory: RegisterSetupDirectory
    setup_admin: SetupFirstAdmin
    login: DirectoryLogin
    authenticate: Authenticate
    logout: Logout
    dev_login: DevLogin


def build_auth_stack(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    directory: FakeDirectoryAuthenticator | None = None,
    *,
    allow_dev_sessions: bool = True,
) -> AuthStack:
    directory = directory or FakeDirectoryAuthenticator()
    throttle = LoginThrottle(
        uow_factory,
        clock,
        secret=THROTTLE_SECRET,
        account_policy=make_policy(max_failures=MAX_PER_ACCOUNT, window=WINDOW, lock_duration=LOCK),
        ip_policy=make_policy(max_failures=MAX_PER_IP, window=WINDOW, lock_duration=LOCK),
    )
    deps = AuthDeps(uow_factory, clock, directory, throttle)
    issue = IssueSession(uow_factory, clock, SESSION_TTL)
    return AuthStack(
        directory=directory,
        throttle=throttle,
        deps=deps,
        issue=issue,
        status=GetAuthStatus(uow_factory),
        register_directory=RegisterSetupDirectory(uow_factory, clock, directory),
        setup_admin=SetupFirstAdmin(deps, issue),
        login=DirectoryLogin(deps, issue),
        authenticate=Authenticate(uow_factory, clock, allow_dev_sessions=allow_dev_sessions),
        logout=Logout(uow_factory, clock),
        dev_login=DevLogin(issue),
    )
