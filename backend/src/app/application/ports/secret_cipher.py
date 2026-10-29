from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.common.secret import SealedSecret


class SecretDecryptionError(Exception):
    """토큰을 풀 수 없다(키가 다르거나 손상). 메시지에 토큰·키를 담지 않는다."""


class SecretCipher(Protocol):
    def seal(self, plaintext: str) -> SealedSecret: ...

    def unseal(self, sealed: SealedSecret) -> str:
        """풀 수 없으면 SecretDecryptionError."""
        ...
