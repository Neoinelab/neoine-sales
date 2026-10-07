"""로그인 도중(IdP로 갔다 돌아오기 전)의 상태를 서명한 문자열로 만든다. 서버에 저장하지 않는다."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.auth.errors import AuthenticationError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock

DEFAULT_TTL_SECONDS = 600
_INVALID = "로그인 요청이 유효하지 않거나 만료되었습니다. 다시 시도하세요"


@dataclass(frozen=True, slots=True)
class PendingLogin:
    state: str
    nonce: str
    code_verifier: str


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class LoginStateCodec:
    def __init__(self, secret: str, clock: Clock, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._key = secret.encode()
        self._clock = clock
        self._ttl = ttl_seconds

    def _sign(self, payload: str) -> str:
        return _b64(hmac.new(self._key, payload.encode(), hashlib.sha256).digest())

    def encode(self, pending: PendingLogin) -> str:
        expires = int(self._clock.now().timestamp()) + self._ttl
        body = {"s": pending.state, "n": pending.nonce, "v": pending.code_verifier, "e": expires}
        payload = _b64(json.dumps(body, separators=(",", ":")).encode())
        return f"{payload}.{self._sign(payload)}"

    def decode(self, token: str) -> PendingLogin:
        parts = token.split(".")
        if len(parts) != 2 or not hmac.compare_digest(self._sign(parts[0]), parts[1]):  # noqa: PLR2004
            raise AuthenticationError(_INVALID)
        try:
            body = json.loads(_unb64(parts[0]))
            expires = int(body["e"])
            pending = PendingLogin(str(body["s"]), str(body["n"]), str(body["v"]))
        except (ValueError, KeyError, TypeError) as error:
            raise AuthenticationError(_INVALID) from error
        if self._clock.now().timestamp() >= expires:
            raise AuthenticationError(_INVALID)
        return pending
