"""SecretCipher Port의 Fernet 구현. 키가 다르거나 토큰이 손상되면 SecretDecryptionError.

오류에는 토큰·키·평문을 싣지 않는다(원인 예외도 잇지 않는다).
"""

from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

from app.application.ports.secret_cipher import SecretDecryptionError
from app.domain.common.secret import SealedSecret

if TYPE_CHECKING:
    from pydantic import SecretStr


class FernetSecretCipher:
    def __init__(self, key: SecretStr) -> None:
        self._fernet = Fernet(key.get_secret_value().encode("ascii"))

    def seal(self, plaintext: str) -> SealedSecret:
        return SealedSecret(self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii"))

    def unseal(self, sealed: SealedSecret) -> str:
        try:
            return self._fernet.decrypt(sealed.token.encode("ascii")).decode("utf-8")
        except InvalidToken, UnicodeError, ValueError:
            raise SecretDecryptionError("저장된 비밀번호를 복호화하지 못했습니다") from None
