from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.application.auth.identity import Identity


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """IdP로 보낼 로그인 요청. state·nonce·code_verifier는 콜백에서 검증하려고 앱이 보관한다."""

    url: str
    state: str
    nonce: str
    code_verifier: str


class IdentityProvider(Protocol):
    async def authorization_request(self) -> AuthorizationRequest:
        """로그인 시작: 사용자를 보낼 URL과 검증용 값을 만든다."""
        ...

    async def complete(self, *, code: str, code_verifier: str, nonce: str) -> Identity:
        """인가 코드를 교환하고 ID 토큰을 검증한다. 실패하면 AuthenticationError."""
        ...
