"""인증 유스케이스 조립 도우미. 단위 테스트와 FakeUseCases가 같은 방식으로 조립한다.

여기서 고정하는 생성자 계약(구현자가 따른다):
- AuthDeps(uow_factory, clock, directory, throttle, cipher, hasher)  app.application.auth.deps
  (cipher: SecretCipher, hasher: PasswordHasher. 새 Port 3개의 Fake는 tests/fakes/{secret_cipher,
  password_hasher,user_password_hashes}.py)
- LoginThrottle(uow_factory, clock, *, secret, account_policy, ip_policy)   ...auth.throttle
- DirectoryLogin(deps, issue_session).execute(*, login_id, password, client_ip) -> LoginOutcome
  (.session: IssuedSession, .directory_warning: DirectoryWarning | None)
- SetupFirstAdmin(deps, issue_session)  execute(...) -> IssuedSession (변경 없음)
- RegisterSetupDirectory(uow_factory, clock, directory, cipher)
- GetAuthStatus(uow_factory), Authenticate(uow_factory, clock)
- DevLogin(uow_factory, clock, issue_session): dev-admin|dev-sales|dev-user 행을 users에 두고 발급
  (allow_dev_sessions는 Authenticate의 allow_dev_users와 VerifyDirectorySettings에 연결된다)

새 Port 3개가 필요한 조각(cipher·hasher·deps·login·setup_admin·register_directory)은
처음 쓸 때 만든다.
그러면 세션 발급·인증·로그아웃·사용자 관리만 쓰는 테스트가 AD 개편 구현에 묶이지 않는다.
"""

from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING

from app.application.auth.auth_status import GetAuthStatus
from app.application.auth.authenticate import Authenticate
from app.application.auth.dev_login import DevLogin
from app.application.auth.issue_session import IssueSession
from app.application.auth.logout import Logout
from app.application.auth.throttle import LoginThrottle
from tests.factories_auth import make_policy
from tests.fakes.directory import FakeDirectoryAuthenticator

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.directory_login import DirectoryLogin
    from app.application.auth.setup_directory import RegisterSetupDirectory
    from app.application.auth.setup_first_admin import SetupFirstAdmin
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.password_hasher import FakePasswordHasher
    from tests.fakes.secret_cipher import FakeSecretCipher

THROTTLE_SECRET = "t" * 40
SESSION_TTL = timedelta(hours=8)
MAX_PER_ACCOUNT = 5
MAX_PER_IP = 30
WINDOW = timedelta(minutes=15)
LOCK = timedelta(minutes=15)


class AuthStack:
    """인증 유스케이스 묶음. directory·throttle·issue·status·authenticate·logout·dev_login은 바로,
    cipher·hasher·deps·register_directory·setup_admin·login은 처음 쓸 때 만든다."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        directory: FakeDirectoryAuthenticator,
        *,
        allow_dev_sessions: bool,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self.directory = directory
        self.throttle = LoginThrottle(
            uow_factory,
            clock,
            secret=THROTTLE_SECRET,
            account_policy=make_policy(
                max_failures=MAX_PER_ACCOUNT, window=WINDOW, lock_duration=LOCK
            ),
            ip_policy=make_policy(max_failures=MAX_PER_IP, window=WINDOW, lock_duration=LOCK),
        )
        self.issue = IssueSession(uow_factory, clock, SESSION_TTL)
        self.status = GetAuthStatus(uow_factory)
        self.authenticate = Authenticate(uow_factory, clock, allow_dev_users=allow_dev_sessions)
        self.logout = Logout(uow_factory, clock)
        self.dev_login = DevLogin(uow_factory, clock, self.issue)

    @cached_property
    def cipher(self) -> FakeSecretCipher:
        from tests.fakes.secret_cipher import FakeSecretCipher  # noqa: PLC0415

        return FakeSecretCipher()

    @cached_property
    def hasher(self) -> FakePasswordHasher:
        from tests.fakes.password_hasher import FakePasswordHasher  # noqa: PLC0415

        return FakePasswordHasher()

    @cached_property
    def deps(self) -> AuthDeps:
        from app.application.auth.deps import AuthDeps  # noqa: PLC0415

        return AuthDeps(
            self._uow_factory, self._clock, self.directory, self.throttle, self.cipher, self.hasher
        )

    @cached_property
    def register_directory(self) -> RegisterSetupDirectory:
        from app.application.auth.setup_directory import RegisterSetupDirectory  # noqa: PLC0415

        return RegisterSetupDirectory(self._uow_factory, self._clock, self.directory, self.cipher)

    @cached_property
    def setup_admin(self) -> SetupFirstAdmin:
        from app.application.auth.setup_first_admin import SetupFirstAdmin  # noqa: PLC0415

        return SetupFirstAdmin(self.deps, self.issue)

    @cached_property
    def login(self) -> DirectoryLogin:
        from app.application.auth.directory_login import DirectoryLogin  # noqa: PLC0415

        return DirectoryLogin(self.deps, self.issue)


def build_auth_stack(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    directory: FakeDirectoryAuthenticator | None = None,
    *,
    allow_dev_sessions: bool = True,
) -> AuthStack:
    return AuthStack(
        uow_factory,
        clock,
        directory or FakeDirectoryAuthenticator(),
        allow_dev_sessions=allow_dev_sessions,
    )
