"""ScryptPasswordHasher: 대체 로그인용 비밀번호 해시(AC13·AC14).

형식 `scrypt$ln=17,r=8,p=1$<salt>$<hash>`(N=2^17, OWASP 최소 권장;
base64, 패딩 없음). 검증은 저장된 문자열의 파라미터로 다시
계산하고, 형식이 깨졌거나 허용 범위 밖이면 예외 없이 False다. 계산은 이벤트 루프를 막지 않도록
스레드에서 한다. 표준 라이브러리 `hashlib.scrypt`를 모듈 속성으로 호출한다(테스트가 호출을 센다).
미검증: 상수 시간 비교(`hmac.compare_digest`)는 시간 측정이 불안정해 코드 리뷰로 확인한다.
"""

import base64
import hashlib
import logging
import re
import threading
import time
from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import Password
from app.domain.auth.password_hash import PasswordHash
from app.infra.crypto.scrypt_hasher import ScryptPasswordHasher

if TYPE_CHECKING:
    from collections.abc import Callable

PASSWORD = "Correct-Horse-1!"  # noqa: S105 - 가짜 값
FORMAT = re.compile(r"scrypt\$ln=17,r=8,p=1\$([A-Za-z0-9+/_-]+)\$([A-Za-z0-9+/_-]+)")
SALT_BYTES = 16
HASH_BYTES = 32
SLOW_LIMIT_SECONDS = 2.0


def _unb64(text: str) -> bytes:
    """표준·URL-safe base64 어느 쪽으로 인코딩했든(패딩 없음) 풀어 준다."""
    normalized = text.replace("-", "+").replace("_", "/")
    return base64.b64decode(normalized + "=" * (-len(normalized) % 4))


def _handmade(  # noqa: PLR0913
    password: str, *, ln: int = 14, r: int = 8, p: int = 1, salt_size: int = 16, size: int = 32
) -> PasswordHash:
    """문서화된 형식으로 직접 만든 해시(구현의 기본 파라미터·base64 종류와 독립).

    솔트·해시의 base64에 `+ / - _`가 들어가면 표준/URL-safe 구분에 따라 달라지므로, 영숫자만 나오는
    솔트를 골라 어느 인코딩 구현으로도 같은 문자열이 되게 한다.
    """
    for attempt in range(200):
        salt = (f"salt{attempt:04d}".encode() * 8)[:salt_size]
        digest = hashlib.scrypt(
            password.encode(), salt=salt, n=2**ln, r=r, p=p, dklen=size, maxmem=256 * 1024 * 1024
        )
        salt_text = base64.b64encode(salt).decode().rstrip("=")
        digest_text = base64.b64encode(digest).decode().rstrip("=")
        if re.fullmatch(r"[A-Za-z0-9]+", salt_text + digest_text):
            return PasswordHash(f"scrypt$ln={ln},r={r},p={p}${salt_text}${digest_text}")
    raise AssertionError("영숫자만 나오는 솔트를 찾지 못했다")


async def test_hash_then_verify_succeeds() -> None:
    """실제 N=2^17 계산으로 왕복하는 유일한 테스트(나머지는 계산만 줄여 호출을 센다)."""
    hasher = ScryptPasswordHasher()

    stored = await hasher.hash(Password(PASSWORD))

    assert isinstance(stored, PasswordHash)
    assert await hasher.verify(Password(PASSWORD), stored) is True


async def test_wrong_password_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()
    stored = await hasher.hash(Password(PASSWORD))

    assert await hasher.verify(Password(PASSWORD + "x"), stored) is False
    assert await hasher.verify(Password("correct-horse-1!"), stored) is False


@pytest.mark.parametrize("text", ["한글 비밀번호!", "a" * 256, " spaced "])
async def test_unusual_passwords_verify(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()
    stored = await hasher.hash(Password(text))

    assert await hasher.verify(Password(text), stored) is True


async def test_same_password_gets_different_salt_each_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()

    first = await hasher.hash(Password(PASSWORD))
    second = await hasher.hash(Password(PASSWORD))

    assert first != second
    assert await hasher.verify(Password(PASSWORD), first)
    assert await hasher.verify(Password(PASSWORD), second)


async def test_encoded_format_contains_parameters_and_no_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _count_scrypt(monkeypatch, fast=True)
    stored = await ScryptPasswordHasher().hash(Password(PASSWORD))

    match = FORMAT.fullmatch(stored.encoded)
    assert match is not None, stored.encoded
    assert len(_unb64(match.group(1))) == SALT_BYTES
    assert len(_unb64(match.group(2))) == HASH_BYTES
    assert "=" not in match.group(1) + match.group(2)  # salt·hash는 패딩 없음
    assert PASSWORD not in stored.encoded
    assert base64.b64encode(PASSWORD.encode()).decode().rstrip("=") not in stored.encoded
    assert len(stored.encoded) <= 512


async def test_new_hashes_use_n_2_17_r_8_p_1_with_enough_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _count_scrypt(monkeypatch, fast=True)

    stored = await ScryptPasswordHasher().hash(Password(PASSWORD))

    assert stored.encoded.startswith("scrypt$ln=17,r=8,p=1$")
    (call,) = calls
    assert (call["n"], call["r"], call["p"]) == (2**17, 8, 1)
    needed = 128 * 2**17 * 8
    assert isinstance(call["maxmem"], int)
    assert call["maxmem"] > needed  # 128MiB 계산이 가능한 값(정확한 값은 구현 자유)


async def test_verify_matches_an_independently_computed_hash() -> None:
    """저장 형식이 문서와 같다: 표준 scrypt 계산 결과를 그대로 받아들인다(N=2^17)."""
    stored = _handmade(PASSWORD, ln=17)

    assert await ScryptPasswordHasher().verify(Password(PASSWORD), stored) is True
    assert await ScryptPasswordHasher().verify(Password("other"), stored) is False


async def test_verify_uses_parameters_from_stored_value() -> None:
    older = _handmade(PASSWORD, ln=12, r=8, p=1, salt_size=8, size=16)

    assert await ScryptPasswordHasher().verify(Password(PASSWORD), older) is True
    assert await ScryptPasswordHasher().verify(Password("other"), older) is False


async def test_legacy_ln_14_hashes_still_verify_with_their_stored_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """local·dev DB에 이미 있는 ln=14 해시는 저장된 파라미터로 검증된다(새 기본값을 쓰지 않는다)."""
    legacy = _handmade(PASSWORD, ln=14)
    calls = _count_scrypt(monkeypatch)

    assert await ScryptPasswordHasher().verify(Password(PASSWORD), legacy) is True
    assert await ScryptPasswordHasher().verify(Password("other"), legacy) is False

    assert [call["n"] for call in calls] == [2**14, 2**14]


@pytest.mark.parametrize(
    "encoded",
    [
        "scrypt$ln=30,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "scrypt$ln=9,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "scrypt$ln=21,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "scrypt$ln=14,r=0,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "scrypt$ln=14,r=17,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "scrypt$ln=14,r=8,p=0$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "scrypt$ln=14,r=8,p=5$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "scrypt$ln=14,r=8,p=1$c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",  # salt 4바이트
        "scrypt$ln=14,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaA",  # hash 4바이트
        "scrypt$ln=14,r=8,p=1$!!!!$????",
        "scrypt$ln=14,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA",  # 구분자 부족
        "scrypt$ln=14,r=8,p=1",
        "scrypt$ln=abc,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "bcrypt$ln=14,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g",
        "plain-text-not-a-hash",
        "$$$",
    ],
)
async def test_malformed_or_out_of_range_parameters_return_false(encoded: str) -> None:
    started = time.monotonic()

    result = await ScryptPasswordHasher().verify(Password(PASSWORD), PasswordHash(encoded))

    assert result is False
    assert time.monotonic() - started < SLOW_LIMIT_SECONDS  # 범위 밖 파라미터로 계산하지 않는다


async def test_oversized_parameters_do_not_compute_scrypt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _count_scrypt(monkeypatch)

    await ScryptPasswordHasher().verify(
        Password(PASSWORD),
        PasswordHash(
            "scrypt$ln=30,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g"
        ),
    )

    assert calls == []


def _count_scrypt(
    monkeypatch: pytest.MonkeyPatch, *, fast: bool = False
) -> list[dict[str, object]]:
    """hashlib.scrypt 호출(인자·스레드)을 기록한다. fast면 실제 계산만 작은 n으로
    바꿔 빠르게 돌린다.

    기록되는 n은 구현이 넘긴 값이다. fast는 같은 입력이면 같은 결과라서 hash/verify 왕복이 맞는다.
    """
    calls: list[dict[str, object]] = []
    real: Callable[..., bytes] = hashlib.scrypt

    def counting(password: bytes, **kwargs: object) -> bytes:
        calls.append({"thread": threading.get_ident(), **kwargs})
        if fast:
            return real(password, **{**kwargs, "n": 16, "maxmem": 0})
        return real(password, **kwargs)

    monkeypatch.setattr(hashlib, "scrypt", counting)
    return calls


async def test_verify_without_stored_hash_returns_false_after_a_dummy_computation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hasher = ScryptPasswordHasher()
    calls = _count_scrypt(monkeypatch, fast=True)
    stored = await hasher.hash(Password(PASSWORD))
    calls.clear()

    assert await hasher.verify(Password("wrong"), stored) is False
    real_cost = calls[-1]["n"]
    assert real_cost == 2**17
    calls.clear()
    assert await hasher.verify(Password(PASSWORD), None) is False

    assert len(calls) == 1  # 해시가 없어도 같은 파라미터로 한 번 계산한다
    assert calls[0]["n"] == real_cost
    assert calls[0]["r"] == 8
    assert calls[0]["p"] == 1


async def test_hash_and_verify_run_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = ScryptPasswordHasher()
    calls = _count_scrypt(monkeypatch, fast=True)
    loop_thread = threading.get_ident()

    stored = await hasher.hash(Password(PASSWORD))
    await hasher.verify(Password(PASSWORD), stored)
    await hasher.verify(Password(PASSWORD), None)

    assert len(calls) == 3
    assert all(call["thread"] != loop_thread for call in calls)


async def test_warning_log_has_no_hash_value_or_password(caplog: pytest.LogCaptureFixture) -> None:
    broken = (
        "scrypt$ln=30,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g"
    )
    caplog.set_level(logging.DEBUG)

    await ScryptPasswordHasher().verify(Password(PASSWORD), PasswordHash(broken))

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert "대체 로그인 해시 형식이 올바르지 않습니다" in warnings
    assert broken not in caplog.text
    assert "c2FsdHNhbHRzYWx0c2FsdA" not in caplog.text
    assert PASSWORD not in caplog.text


async def test_valid_hash_verification_logs_nothing_sensitive(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()
    caplog.set_level(logging.DEBUG)

    stored = await hasher.hash(Password(PASSWORD))
    await hasher.verify(Password(PASSWORD), stored)

    assert PASSWORD not in caplog.text
    assert stored.encoded not in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
