"""ScryptPasswordHasher: 대체 로그인용 비밀번호 해시.

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
    """실제 N=2^17 계산으로 해시한 뒤 검증하면 성공한다(실제 계산 왕복은 이 테스트뿐이다)."""
    # given: 해시기
    hasher = ScryptPasswordHasher()

    # when: 비밀번호를 해시한다
    stored = await hasher.hash(Password(PASSWORD))

    # then: 해시 객체이고 같은 비밀번호 검증이 성공한다
    assert isinstance(stored, PasswordHash)
    assert await hasher.verify(Password(PASSWORD), stored) is True


async def test_wrong_password_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """틀린 비밀번호나 대소문자만 다른 비밀번호는 검증에 실패한다."""
    # given: 계산을 줄인 해시기와 저장된 해시
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()
    stored = await hasher.hash(Password(PASSWORD))

    # when: 다른 비밀번호들로 검증한다
    result = await hasher.verify(Password(PASSWORD + "x"), stored)
    # then: 모두 False다
    assert result is False
    assert await hasher.verify(Password("correct-horse-1!"), stored) is False


@pytest.mark.parametrize("text", ["한글 비밀번호!", "a" * 256, " spaced "])
async def test_unusual_passwords_verify(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """한글·최대 길이·공백 포함 비밀번호도 검증된다."""
    # given: 계산을 줄인 해시기와 특이한 비밀번호의 해시
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()
    stored = await hasher.hash(Password(text))

    # when: 같은 비밀번호로 검증한다
    result = await hasher.verify(Password(text), stored)
    # then: True다
    assert result is True


async def test_same_password_gets_different_salt_each_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """같은 비밀번호도 해시할 때마다 솔트가 달라진다."""
    # given: 계산을 줄인 해시기
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()

    # when: 같은 비밀번호를 두 번 해시한다
    first = await hasher.hash(Password(PASSWORD))
    second = await hasher.hash(Password(PASSWORD))

    # then: 해시 문자열은 다르지만 둘 다 검증된다
    assert first != second
    assert await hasher.verify(Password(PASSWORD), first)
    assert await hasher.verify(Password(PASSWORD), second)


async def test_encoded_format_contains_parameters_and_no_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """저장 형식은 파라미터를 담고 평문을 포함하지 않는다."""
    # given: 계산을 줄인 해시기
    _count_scrypt(monkeypatch, fast=True)
    # when: 비밀번호를 해시한다
    stored = await ScryptPasswordHasher().hash(Password(PASSWORD))

    # then: 형식이 정해진 패턴과 같고 솔트·해시 길이가 맞다
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
    """새 해시는 N=2^17, r=8, p=1과 충분한 메모리 한도를 쓴다."""
    # given: scrypt 호출을 기록하는 해시 환경
    calls = _count_scrypt(monkeypatch, fast=True)

    # when: 비밀번호를 해시한다
    stored = await ScryptPasswordHasher().hash(Password(PASSWORD))

    # then: 형식 접두사와 호출 파라미터가 정해진 값이다
    assert stored.encoded.startswith("scrypt$ln=17,r=8,p=1$")
    (call,) = calls
    assert (call["n"], call["r"], call["p"]) == (2**17, 8, 1)
    needed = 128 * 2**17 * 8
    assert isinstance(call["maxmem"], int)
    assert call["maxmem"] > needed  # 128MiB 계산이 가능한 값(정확한 값은 구현 자유)


async def test_verify_matches_an_independently_computed_hash() -> None:
    """독립적으로 계산한 표준 scrypt 해시도 검증된다."""
    # given: 문서화된 형식으로 직접 만든 N=2^17 해시
    stored = _handmade(PASSWORD, ln=17)

    # when: 저장된 해시를 맞는 비밀번호로 검증한다
    result = await ScryptPasswordHasher().verify(Password(PASSWORD), stored)
    # then: True다
    assert result is True
    assert await ScryptPasswordHasher().verify(Password("other"), stored) is False


async def test_verify_uses_parameters_from_stored_value() -> None:
    """검증은 저장된 값의 파라미터를 쓴다."""
    # given: 다른 파라미터로 직접 만든 해시
    older = _handmade(PASSWORD, ln=12, r=8, p=1, salt_size=8, size=16)

    # when: 이전 비용 해시를 맞는 비밀번호로 검증한다
    result = await ScryptPasswordHasher().verify(Password(PASSWORD), older)
    # then: True다
    assert result is True
    assert await ScryptPasswordHasher().verify(Password("other"), older) is False


async def test_legacy_ln_14_hashes_still_verify_with_their_stored_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """기존 ln=14 해시는 저장된 파라미터로 계속 검증된다(새 기본값을 쓰지 않는다)."""
    # given: ln=14 해시
    legacy = _handmade(PASSWORD, ln=14)
    # given: scrypt 호출 기록
    calls = _count_scrypt(monkeypatch)

    # when: 옛 형식 해시를 맞는 비밀번호로 검증한다
    result = await ScryptPasswordHasher().verify(Password(PASSWORD), legacy)
    # then: True다
    assert result is True
    assert await ScryptPasswordHasher().verify(Password("other"), legacy) is False

    # then: 두 호출 모두 2^14로 계산했다
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
    """형식이 깨졌거나 파라미터가 범위 밖이면 예외 없이 False다."""
    # given: 시작 시각
    started = time.monotonic()

    # when: 깨진 해시로 검증한다
    result = await ScryptPasswordHasher().verify(Password(PASSWORD), PasswordHash(encoded))

    # then: False이고 범위 밖 파라미터로 계산하지 않아 빠르게 끝난다
    assert result is False
    assert time.monotonic() - started < SLOW_LIMIT_SECONDS  # 범위 밖 파라미터로 계산하지 않는다


async def test_oversized_parameters_do_not_compute_scrypt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """너무 큰 파라미터면 scrypt를 계산하지 않는다."""
    # given: scrypt 호출 기록
    calls = _count_scrypt(monkeypatch)

    # when: ln=30인 해시로 검증한다
    await ScryptPasswordHasher().verify(
        Password(PASSWORD),
        PasswordHash(
            "scrypt$ln=30,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g"
        ),
    )

    # then: scrypt를 호출하지 않았다
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
    """저장된 해시가 없으면 같은 비용의 더미 계산 뒤 False를 돌려준다."""
    # given: 계산을 줄인 해시기와 저장된 해시
    hasher = ScryptPasswordHasher()
    calls = _count_scrypt(monkeypatch, fast=True)
    stored = await hasher.hash(Password(PASSWORD))
    calls.clear()

    # when: 틀린 비밀번호로 검증해 실제 비용을 확인한다
    assert await hasher.verify(Password("wrong"), stored) is False
    real_cost = calls[-1]["n"]
    assert real_cost == 2**17
    calls.clear()
    # when: 해시 없이 검증한다
    assert await hasher.verify(Password(PASSWORD), None) is False

    # then: 같은 파라미터로 한 번 계산했다
    assert len(calls) == 1  # 해시가 없어도 같은 파라미터로 한 번 계산한다
    assert calls[0]["n"] == real_cost
    assert calls[0]["r"] == 8
    assert calls[0]["p"] == 1


async def test_hash_and_verify_run_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """해시와 검증은 이벤트 루프 밖 스레드에서 실행된다."""
    # given: 계산을 기록하는 해시기
    hasher = ScryptPasswordHasher()
    calls = _count_scrypt(monkeypatch, fast=True)
    loop_thread = threading.get_ident()

    # when: 해시하고 두 번 검증한다
    stored = await hasher.hash(Password(PASSWORD))
    await hasher.verify(Password(PASSWORD), stored)
    await hasher.verify(Password(PASSWORD), None)

    # then: 세 번의 계산이 모두 루프 스레드가 아닌 곳에서 실행됐다
    assert len(calls) == 3
    assert all(call["thread"] != loop_thread for call in calls)


async def test_warning_log_has_no_hash_value_or_password(caplog: pytest.LogCaptureFixture) -> None:
    """경고 로그에는 해시 값이나 비밀번호가 없다."""
    # given: 파라미터가 범위 밖인 해시와 로그 수집
    broken = (
        "scrypt$ln=30,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g"
    )
    caplog.set_level(logging.DEBUG)

    # when: 그 해시로 검증한다
    await ScryptPasswordHasher().verify(Password(PASSWORD), PasswordHash(broken))

    # then: 형식 경고만 남고 해시 값·비밀번호는 로그에 없다
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert "대체 로그인 해시 형식이 올바르지 않습니다" in warnings
    assert broken not in caplog.text
    assert "c2FsdHNhbHRzYWx0c2FsdA" not in caplog.text
    assert PASSWORD not in caplog.text


async def test_valid_hash_verification_logs_nothing_sensitive(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """정상 검증은 민감한 값을 로그에 남기지 않는다."""
    # given: 계산을 줄인 해시기와 로그 수집
    _count_scrypt(monkeypatch, fast=True)
    hasher = ScryptPasswordHasher()
    caplog.set_level(logging.DEBUG)

    # when: 해시하고 검증한다
    stored = await hasher.hash(Password(PASSWORD))
    await hasher.verify(Password(PASSWORD), stored)

    # then: 비밀번호·해시가 로그에 없고 경고 이상 기록도 없다
    assert PASSWORD not in caplog.text
    assert stored.encoded not in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
