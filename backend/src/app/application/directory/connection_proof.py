import hashlib
import hmac
import json
from typing import TYPE_CHECKING, Final

from app.application.ports.secret_cipher import SecretDecryptionError
from app.domain.common.errors import InvalidValueError
from app.domain.directory import rules
from app.domain.directory.settings import BASE_DN_MAX

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.secret_cipher import SecretCipher
    from app.domain.common.secret import SealedSecret
    from app.domain.directory.settings import DirectoryConnection

PROOF_TTL_SECONDS: Final = 600
_PAYLOAD_LENGTH: Final = 4
RETEST_REQUIRED: Final = "연결 테스트 결과가 없거나 만료되었습니다. 다시 연결 테스트를 수행하세요."


def _fingerprint(connection: DirectoryConnection) -> str:
    value = json.dumps(
        [
            connection.host,
            connection.port,
            connection.security.value,
            connection.user_filter,
            connection.connect_timeout_seconds,
        ]
    )
    return hashlib.sha256(value.encode()).hexdigest()


class DirectoryConnectionProof:
    def __init__(self, cipher: SecretCipher, clock: Clock) -> None:
        self._cipher = cipher
        self._clock = clock

    def issue(self, connection: DirectoryConnection, base_dn: str, scope: str) -> str:
        expires = int(self._clock.now().timestamp()) + PROOF_TTL_SECONDS
        payload = json.dumps([_fingerprint(connection), base_dn, scope, expires])
        return self._cipher.seal(payload).token

    def verify(self, connection: DirectoryConnection, token: SealedSecret, scope: str) -> str:
        try:
            payload = json.loads(self._cipher.unseal(token))
        except SecretDecryptionError, json.JSONDecodeError:
            raise InvalidValueError(RETEST_REQUIRED) from None
        if not isinstance(payload, list) or len(payload) != _PAYLOAD_LENGTH:
            raise InvalidValueError(RETEST_REQUIRED)
        fingerprint, base_dn, owner, expires = payload
        if (
            not isinstance(fingerprint, str)
            or not isinstance(base_dn, str)
            or not isinstance(owner, str)
            or type(expires) is not int
            or not hmac.compare_digest(fingerprint.encode(), _fingerprint(connection).encode())
            or owner != scope
            or expires <= self._clock.now().timestamp()
        ):
            raise InvalidValueError(RETEST_REQUIRED)
        rules.check_text(base_dn, "base_dn", max_length=BASE_DN_MAX)
        return base_dn
