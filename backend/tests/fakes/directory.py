"""DirectoryAuthenticator Port의 Fake. 호출 내용을 기록하고, 계정은 add_account로 등록한다.

실제 어댑터와 같은 의미를 따른다: 사용자를 못 찾으면 InvalidCredentialsError(SEARCH), 비밀번호가
틀리면 InvalidCredentialsError(BIND). 서비스 계정 바인드·연결 실패 같은 장애는
`discover_fails_with`·`authenticate_fails_with`(또는 둘 다 정하는 `fail_all_with`)로 주입한다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.ports.directory import (
    DirectoryError,
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)
from tests.factories_auth import BASE_DN

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.directory.settings import DirectorySettings


@dataclass(frozen=True, slots=True)
class AuthenticateCall:
    settings: DirectorySettings
    base_dn: str
    login_id: LoginId
    password: str  # 테스트용 더미 값을 단언할 때만 쓴다


class FakeDirectoryAuthenticator:
    def __init__(self) -> None:
        self._accounts: dict[str, tuple[str, DirectoryUser]] = {}
        self.base_dn = BASE_DN  # discover_base_dn이 찾아 주는 값
        self.discover_fails_with: DirectoryError | None = None
        self.authenticate_fails_with: DirectoryError | None = None
        self.discover_calls: list[DirectorySettings] = []
        self.authenticate_calls: list[AuthenticateCall] = []

    def add_account(
        self,
        login_id: str,
        password: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
    ) -> None:
        user = DirectoryUser(login_id=login_id, display_name=display_name or login_id, email=email)
        self._accounts[login_id] = (password, user)

    def fail_all_with(self, error: DirectoryError | None) -> None:
        """Base DN 탐색과 사용자 인증이 모두 같은 장애로 실패(None이면 복구)."""
        self.discover_fails_with = error
        self.authenticate_fails_with = error

    async def discover_base_dn(self, settings: DirectorySettings) -> str:
        self.discover_calls.append(settings)
        if self.discover_fails_with is not None:
            raise self.discover_fails_with
        return self.base_dn

    async def authenticate(
        self, settings: DirectorySettings, base_dn: str, login_id: LoginId, password: Password
    ) -> DirectoryUser:
        self.authenticate_calls.append(
            AuthenticateCall(settings, base_dn, login_id, password.reveal())
        )
        if self.authenticate_fails_with is not None:
            raise self.authenticate_fails_with
        account = self._accounts.get(login_id.value)
        if account is None:  # 검색 결과 0건
            raise InvalidCredentialsError(stage=VerificationStage.SEARCH)
        if account[0] != password.reveal():  # 사용자 비밀번호 바인드 거부
            raise InvalidCredentialsError(stage=VerificationStage.BIND)
        return account[1]
