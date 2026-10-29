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
    SERVICE_BIND = "service_bind"  # 서비스 계정 바인드
    BASE_DN = "base_dn"  # RootDSE defaultNamingContext
    SEARCH = "search"  # 사용자 검색(0건은 InvalidCredentials, 2건 이상은 Misconfigured)
    BIND = "bind"  # 사용자(admin) 비밀번호 바인드


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
    """설정(서비스 계정·Base DN·필터 등)이 서버와 맞지 않는다."""


class DirectoryAuthenticator(Protocol):
    async def discover_base_dn(self, settings: DirectorySettings) -> str:
        """연결(+TLS) -> 서비스 계정 바인드 -> RootDSE defaultNamingContext를 읽어 돌려준다.

        실패: DirectoryUnavailableError(CONNECT|TLS|SERVICE_BIND),
        DirectoryMisconfiguredError(SERVICE_BIND|BASE_DN).
        """
        ...

    async def authenticate(
        self, settings: DirectorySettings, base_dn: str, login_id: LoginId, password: Password
    ) -> DirectoryUser:
        """서비스 계정으로 사용자를 찾고(search) 찾은 DN과 비밀번호로 바인드한다(search-then-bind).

        0건·사용자 비밀번호 거부는 InvalidCredentialsError(SEARCH|BIND), 2건 이상은
        DirectoryMisconfiguredError(SEARCH), 서비스 계정 거부는
        DirectoryMisconfiguredError(SERVICE_BIND), 연결·TLS는 DirectoryUnavailableError.
        """
        ...
