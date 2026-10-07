import hashlib
import secrets


def new_token() -> str:
    """추측할 수 없는 세션 토큰(256비트 난수)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """저장소에는 토큰 자체가 아니라 SHA-256 해시만 둔다(DB가 새도 세션을 탈취할 수 없다)."""
    return hashlib.sha256(token.encode()).hexdigest()
