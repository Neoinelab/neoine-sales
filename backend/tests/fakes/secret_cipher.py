"""SecretCipher Port의 Fake. 되돌릴 수 있는 가짜 변환이며 토큰에 평문이 그대로 들어 있지 않다.

`fail_unseal=True`면 키가 바뀐 상황처럼 모든 unseal이 SecretDecryptionError로 실패한다.
"""

from app.application.ports.secret_cipher import SecretDecryptionError
from app.domain.common.secret import SealedSecret

PREFIX = "fake-sealed:"
FOREIGN_TOKEN = "sealed-with-another-key"  # noqa: S105 - 가짜 값. 이 Fake가 만든 토큰이 아니다


class FakeSecretCipher:
    def __init__(self) -> None:
        self.fail_unseal = False

    def seal(self, plaintext: str) -> SealedSecret:
        return SealedSecret(PREFIX + plaintext[::-1].encode().hex())

    def unseal(self, sealed: SealedSecret) -> str:
        if self.fail_unseal or not sealed.token.startswith(PREFIX):
            raise SecretDecryptionError("복호화하지 못했습니다")
        return bytes.fromhex(sealed.token[len(PREFIX) :]).decode()[::-1]


def foreign_secret() -> SealedSecret:
    """다른 키로 봉인된 것처럼 이 Fake가 풀 수 없는 토큰."""
    return SealedSecret(FOREIGN_TOKEN)
