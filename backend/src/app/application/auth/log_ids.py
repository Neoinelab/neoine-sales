import hashlib


def short_hash(value: str) -> str:
    """로그에 원문 대신 남길 식별용 해시(앞 12자)."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]
