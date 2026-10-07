from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.auth.login_state import PendingLogin

if TYPE_CHECKING:
    from app.application.auth.login_state import LoginStateCodec
    from app.application.ports.identity_provider import IdentityProvider


@dataclass(frozen=True, slots=True)
class LoginStart:
    redirect_url: str
    pending_token: str  # 콜백에서 state·nonce를 검증하려고 브라우저(쿠키)에 맡기는 서명된 값


class BeginLogin:
    def __init__(self, idp: IdentityProvider, codec: LoginStateCodec) -> None:
        self._idp = idp
        self._codec = codec

    async def execute(self) -> LoginStart:
        request = await self._idp.authorization_request()
        pending = PendingLogin(request.state, request.nonce, request.code_verifier)
        return LoginStart(request.url, self._codec.encode(pending))
