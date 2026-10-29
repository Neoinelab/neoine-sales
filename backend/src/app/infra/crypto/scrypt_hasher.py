"""PasswordHasher Port의 scrypt 구현(표준 라이브러리 hashlib.scrypt).

저장 형식은 `scrypt$ln=17,r=8,p=1$<salt>$<hash>`(표준 base64, 패딩 없음)이다. 검증은 저장된 문자열의
파라미터로 다시 계산하므로 이후에 기본값을 올려도 예전 해시가 유효하다. 범위 밖 파라미터는 계산하지
않고 False다(저장 값 변조로 인한 CPU·메모리 소진 방지). 계산은 이벤트 루프를 막지 않도록 스레드에서
한다. 로그와 예외에는 해시·비밀번호를 쓰지 않는다.
"""

import asyncio
import base64
import binascii
import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.auth.password_hash import PasswordHash

if TYPE_CHECKING:
    from app.domain.auth.credentials import Password

logger = logging.getLogger(__name__)

SCHEME = "scrypt"
LOG_N = 17  # N=2^17 (사용자 결정 2026-10-29). 이미 저장된 ln=14 해시는 저장 파라미터로 검증된다
R = 8
P = 1
SALT_BYTES = 16
HASH_BYTES = 32
MAXMEM = (
    256 * 1024 * 1024
)  # 작업 메모리(128*n*r=128MiB at 기본값)보다 넉넉한 상한. 초과 파라미터는 거부

_LN_RANGE = range(10, 21)
_R_RANGE = range(1, 17)
_P_RANGE = range(1, 5)
_SALT_RANGE = range(8, 65)
_HASH_RANGE = range(16, 65)
_PARAMS = re.compile(r"ln=(\d{1,2}),r=(\d{1,2}),p=(\d{1,2})")
_B64 = re.compile(r"[A-Za-z0-9+/_-]+")


@dataclass(frozen=True, slots=True)
class _Params:
    n: int
    r: int
    p: int
    salt: bytes
    size: int


@dataclass(frozen=True, slots=True)
class _Parsed:
    params: _Params
    digest: bytes


_DEFAULT_COST = (2**LOG_N, R, P)
_DUMMY = _Params(*_DEFAULT_COST, salt=b"\x00" * SALT_BYTES, size=HASH_BYTES)


def _encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii").rstrip("=")


def _decode(text: str) -> bytes | None:
    if _B64.fullmatch(text) is None:
        return None
    normalized = text.replace("-", "+").replace("_", "/")
    try:
        return base64.b64decode(normalized + "=" * (-len(normalized) % 4), validate=True)
    except binascii.Error, ValueError:
        return None


def _parse(encoded: str) -> _Parsed | None:
    parts = encoded.split("$")
    if len(parts) != 4 or parts[0] != SCHEME:  # noqa: PLR2004
        return None
    match = _PARAMS.fullmatch(parts[1])
    salt, digest = _decode(parts[2]), _decode(parts[3])
    if match is None or salt is None or digest is None:
        return None
    ln, r, p = (int(group) for group in match.groups())
    in_range = ln in _LN_RANGE and r in _R_RANGE and p in _P_RANGE
    if not in_range or len(salt) not in _SALT_RANGE or len(digest) not in _HASH_RANGE:
        return None
    if 128 * (2**ln) * r + 128 * r * p > MAXMEM:
        return None
    return _Parsed(_Params(2**ln, r, p, salt, len(digest)), digest)


def _compute(password: str, params: _Params) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=params.salt,
        n=params.n,
        r=params.r,
        p=params.p,
        dklen=params.size,
        maxmem=MAXMEM,
    )


def _hash(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = _compute(password, _Params(*_DEFAULT_COST, salt=salt, size=HASH_BYTES))
    return f"{SCHEME}$ln={LOG_N},r={R},p={P}${_encode(salt)}${_encode(digest)}"


def _verify(password: str, stored: str | None) -> bool:
    if stored is None:
        _compute(password, _DUMMY)
        return False
    parsed = _parse(stored)
    if parsed is None:
        logger.warning("대체 로그인 해시 형식이 올바르지 않습니다")
        return False
    digest = _compute(password, parsed.params)
    return hmac.compare_digest(digest, parsed.digest)


class ScryptPasswordHasher:
    async def hash(self, password: Password) -> PasswordHash:
        return PasswordHash(await asyncio.to_thread(_hash, password.reveal()))

    async def verify(self, password: Password, stored: PasswordHash | None) -> bool:
        encoded = stored.encoded if stored is not None else None
        return await asyncio.to_thread(_verify, password.reveal(), encoded)
