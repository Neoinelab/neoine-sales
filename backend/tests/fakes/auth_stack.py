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
- TestSetupDirectory(uow_factory, directory)  execute(settings) -> TestResult (setup_directory.py)
- GetAuthStatus(uow_factory), Authenticate(uow_factory, clock)

앱 자체 계정 관리(local 모드) 개편 계약(구현자가 따른다).
AD 경로 클래스는 그대로 두고 새 클래스를 더한다:
- ChooseSetupAuthMode(uow_factory, clock)      app.application.auth.setup_auth_mode
  execute(mode: AuthMode) -> AuthSettings
- LocalLogin(deps)                              ...auth.local_login
  execute(account: LoginId, password: Password) -> Principal
- PasswordLogin(deps, issue_session)            ...auth.password_login
  execute(*, login_id, password, client_ip) -> LoginOutcome
  (모드 LOCAL이면 LocalLogin, 그 외 DirectoryLogin)
- SetupFirstLocalAdmin(deps, issue_session)     ...auth.setup_first_local_admin
  execute(*, login_id, password, display_name=None, email=None, phone=None) -> IssuedSession
- SetupAdmin(deps, issue_session)               ...auth.setup_admin
  (모드 LOCAL이면 위, 그 외 SetupFirstAdmin)
  execute(*, login_id, password, client_ip, display_name=None, email=None, phone=None)
  -> IssuedSession
- ChangeMyPassword(deps)                        app.application.account.change_my_password
  execute(*, actor, current, new, session_token, client_ip) -> None
- 모드 헬퍼 current_mode(uow) -> AuthMode | None  ...auth.mode  (effective_mode 위에서 계산)

새 Port 3개가 필요한 조각(cipher·hasher·deps·login·setup_admin·register_directory)은
처음 쓸 때 만든다.
그러면 세션 발급·인증·로그아웃·사용자 관리만 쓰는 테스트가 AD 개편 구현에 묶이지 않는다.
"""

from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING

from app.application.auth.auth_status import GetAuthStatus
from app.application.auth.authenticate import Authenticate
from app.application.auth.issue_session import IssueSession
from app.application.auth.logout import Logout
from app.application.auth.throttle import LoginThrottle
from app.application.directory.connection_proof import DirectoryConnectionProof
from app.application.directory.verify_settings import VerifyDirectorySettings
from tests.factories_auth import make_policy
from tests.fakes.directory import FakeDirectoryAuthenticator

if TYPE_CHECKING:
    from app.application.account.change_my_password import ChangeMyPassword
    from app.application.auth.deps import AuthDeps
    from app.application.auth.directory_login import DirectoryLogin
    from app.application.auth.local_login import LocalLogin
    from app.application.auth.password_login import PasswordLogin
    from app.application.auth.setup_admin import SetupAdmin
    from app.application.auth.setup_auth_mode import ChooseSetupAuthMode
    from app.application.auth.setup_directory import RegisterSetupDirectory, TestSetupDirectory
    from app.application.auth.setup_first_admin import SetupFirstAdmin
    from app.application.auth.setup_first_local_admin import SetupFirstLocalAdmin
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
    """인증 유스케이스 묶음. directory·throttle·issue·status·authenticate·logout은 바로,
    cipher·hasher·deps·register_directory·setup_admin·login은 처음 쓸 때 만든다."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        directory: FakeDirectoryAuthenticator,
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
        self.authenticate = Authenticate(uow_factory, clock)
        self.logout = Logout(uow_factory, clock)

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

        return RegisterSetupDirectory(
            self._uow_factory, self._clock, DirectoryConnectionProof(self.cipher, self._clock)
        )

    @cached_property
    def test_setup_directory(self) -> TestSetupDirectory:
        from app.application.auth.setup_directory import TestSetupDirectory  # noqa: PLC0415

        return TestSetupDirectory(
            self._uow_factory,
            VerifyDirectorySettings(
                self.directory, DirectoryConnectionProof(self.cipher, self._clock)
            ),
        )

    @cached_property
    def setup_admin(self) -> SetupFirstAdmin:
        from app.application.auth.setup_first_admin import SetupFirstAdmin  # noqa: PLC0415

        return SetupFirstAdmin(self.deps, self.issue)

    @cached_property
    def login(self) -> DirectoryLogin:
        from app.application.auth.directory_login import DirectoryLogin  # noqa: PLC0415

        return DirectoryLogin(self.deps, self.issue)

    # ---- 앱 자체 계정 관리(local 모드): 처음 쓸 때 만든다(구현 전에도 기존 테스트가 수집된다) ----

    @cached_property
    def choose_mode(self) -> ChooseSetupAuthMode:
        from app.application.auth.setup_auth_mode import ChooseSetupAuthMode  # noqa: PLC0415

        return ChooseSetupAuthMode(self._uow_factory, self._clock)

    @cached_property
    def local_login(self) -> LocalLogin:
        from app.application.auth.local_login import LocalLogin  # noqa: PLC0415

        return LocalLogin(self.deps)

    @cached_property
    def password_login(self) -> PasswordLogin:
        from app.application.auth.password_login import PasswordLogin  # noqa: PLC0415

        return PasswordLogin(self.deps, self.issue)

    @cached_property
    def setup_local_admin(self) -> SetupFirstLocalAdmin:
        from app.application.auth.setup_first_local_admin import (  # noqa: PLC0415
            SetupFirstLocalAdmin,
        )

        return SetupFirstLocalAdmin(self.deps, self.issue)

    @cached_property
    def setup(self) -> SetupAdmin:
        from app.application.auth.setup_admin import SetupAdmin  # noqa: PLC0415

        return SetupAdmin(self.deps, self.issue)

    @cached_property
    def change_my_password(self) -> ChangeMyPassword:
        from app.application.account.change_my_password import ChangeMyPassword  # noqa: PLC0415

        return ChangeMyPassword(self.deps)


def build_auth_stack(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    directory: FakeDirectoryAuthenticator | None = None,
) -> AuthStack:
    return AuthStack(uow_factory, clock, directory or FakeDirectoryAuthenticator())
