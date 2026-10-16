"""DirectoryAuthenticator Port의 Fake. 호출 내용을 기록하고, 계정은 add_account로 등록한다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.ports.directory import (
    DirectoryError,
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.directory.settings import DirectorySettings


@dataclass(frozen=True, slots=True)
class AuthenticateCall:
    settings: DirectorySettings
    login_id: LoginId
    password: str  # 테스트용 더미 값을 단언할 때만 쓴다


class FakeDirectoryAuthenticator:
    def __init__(self) -> None:
        self._accounts: dict[str, tuple[str, DirectoryUser]] = {}
        self.fail_with: DirectoryError | None = None
        self.probe_fails_with: DirectoryError | None = None
        self.authenticate_calls: list[AuthenticateCall] = []
        self.probe_calls: list[DirectorySettings] = []

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

    async def authenticate(
        self, settings: DirectorySettings, login_id: LoginId, password: Password
    ) -> DirectoryUser:
        self.authenticate_calls.append(AuthenticateCall(settings, login_id, password.reveal()))
        if self.fail_with is not None:
            raise self.fail_with
        account = self._accounts.get(login_id.value)
        if account is None or account[0] != password.reveal():
            raise InvalidCredentialsError(stage=VerificationStage.BIND)
        return account[1]

    async def probe(self, settings: DirectorySettings) -> None:
        self.probe_calls.append(settings)
        if self.probe_fails_with is not None:
            raise self.probe_fails_with
