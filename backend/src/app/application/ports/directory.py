from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.directory.settings import DirectorySettings


@dataclass(frozen=True, slots=True)
class DirectoryUser:
    """디렉터리가 인증해 준 사용자. 표시 이름·메일은 디렉터리 값이다."""

    login_id: str
    display_name: str
    email: str | None


class VerificationStage(StrEnum):
    CONNECT = "connect"
    TLS = "tls"
    BIND = "bind"
    SEARCH = "search"


class DirectoryError(Exception):
    """디렉터리 통신 실패의 기반 예외. 메시지·속성에 비밀번호를 담지 않는다."""

    def __init__(self, message: str = "", *, stage: VerificationStage | None = None) -> None:
        super().__init__(message)
        self.stage = stage


class InvalidCredentialsError(DirectoryError):
    """아이디·비밀번호가 틀렸거나 디렉터리에서 사용자를 찾지 못했다."""


class DirectoryUnavailableError(DirectoryError):
    """연결·TLS·타임아웃 등으로 디렉터리와 통신하지 못했다."""


class DirectoryMisconfiguredError(DirectoryUnavailableError):
    """설정(바인드 템플릿·Base DN·필터 등)이 서버와 맞지 않는다."""


class DirectoryAuthenticator(Protocol):
    async def authenticate(
        self, settings: DirectorySettings, login_id: LoginId, password: Password
    ) -> DirectoryUser:
        """사용자 자격증명으로 바인드해 인증하고 표시 이름·메일을 읽는다.

        자격증명 오류는 InvalidCredentialsError, 그 밖의 실패는 DirectoryUnavailableError /
        DirectoryMisconfiguredError(stage 포함).
        """
        ...

    async def probe(self, settings: DirectorySettings) -> None:
        """바인드 없이 설정된 서버와 TCP·TLS 연결만 확인한다. 실패하면 DirectoryUnavailableError."""
        ...
