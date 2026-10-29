"""APP_SETTINGS_ENCRYPTION_KEY: AD 바인드 비밀번호 암호화 키 설정 검증 (AC9).

모든 프로파일에서 필수이고 Fernet 키 형식(URL-safe base64로 풀면 32바이트)이어야 한다. product는
`.env.example`에 적힌 예시 키를 거부한다. 오류 메시지에 키 값이 나오지 않는다. 키는 jwt_secret과
별개다(JWT 키 교체가 저장된 비밀번호를 깨뜨리지 않게).
"""

import base64
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.config.profiles import (
    EXAMPLE_SETTINGS_ENCRYPTION_KEY,
    DevSettings,
    LocalSettings,
    ProductSettings,
)
from tests.support.crypto_keys import TEST_FERNET_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator

BACKEND = Path(__file__).resolve().parents[2]
BASE_ENV = {
    "APP_DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/app",
    "APP_JWT_SECRET": "x" * 40,
}
PRODUCT_ENV = {
    "APP_PROFILE": "product",
    "APP_SENTRY_DSN": "https://key@sentry.internal.example.com/1",
    "APP_CORS_ALLOWED_ORIGINS": '["https://sales.internal.example.com"]',
}
PROFILE_ENVS = {
    "local": {},
    "dev": {"APP_PROFILE": "dev"},
    "product": PRODUCT_ENV,
}
FERNET_KEY_BYTES = 32


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    for key in [k for k in os.environ if k.startswith("APP_")]:
        monkeypatch.delenv(key)
    for key, value in BASE_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("profile", list(PROFILE_ENVS))
def test_missing_encryption_key_fails_in_every_profile(
    monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    _set(monkeypatch, PROFILE_ENVS[profile])

    with pytest.raises(ValidationError, match="settings_encryption_key"):
        get_settings()


def test_the_jwt_secret_is_not_reused_as_the_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_JWT_SECRET", TEST_FERNET_KEY)  # jwt_secret만 있으면 부족하다

    with pytest.raises(ValidationError, match="settings_encryption_key"):
        get_settings()


@pytest.mark.parametrize(
    ("profile", "settings_type"),
    [("local", LocalSettings), ("dev", DevSettings), ("product", ProductSettings)],
)
def test_a_valid_key_is_accepted_and_kept_secret(
    monkeypatch: pytest.MonkeyPatch, profile: str, settings_type: type
) -> None:
    _set(monkeypatch, {**PROFILE_ENVS[profile], "APP_SETTINGS_ENCRYPTION_KEY": TEST_FERNET_KEY})

    settings = get_settings()

    assert isinstance(settings, settings_type)
    assert settings.settings_encryption_key.get_secret_value() == TEST_FERNET_KEY
    assert TEST_FERNET_KEY not in repr(settings)
    assert TEST_FERNET_KEY not in str(settings)


MALFORMED = {
    "empty": "",
    "short-text": "short",
    "not-base64": "!" * 44,
    "16-bytes": base64.urlsafe_b64encode(b"k" * 16).decode(),
    "31-bytes": base64.urlsafe_b64encode(b"k" * 31).decode(),
    "33-bytes": base64.urlsafe_b64encode(b"k" * 33).decode(),
    "40-chars-of-text": "x" * 40,
    # 알파벳 밖 문자가 섞인 값은 조용히 버려져 통과하면 안 된다
    "dot-inside-valid-key": TEST_FERNET_KEY[:10] + "." + TEST_FERNET_KEY[10:],
    "space-inside-valid-key": TEST_FERNET_KEY[:10] + " " + TEST_FERNET_KEY[10:],
    "newline-inside-valid-key": TEST_FERNET_KEY[:10] + "\n" + TEST_FERNET_KEY[10:],
    "plus-slash-alphabet": TEST_FERNET_KEY[:10] + "+/" + TEST_FERNET_KEY[12:],
}


@pytest.mark.parametrize("name", list(MALFORMED))
@pytest.mark.parametrize("profile", ["local", "product"])
def test_malformed_encryption_key_fails_without_echoing_the_value(
    monkeypatch: pytest.MonkeyPatch, profile: str, name: str
) -> None:
    value = MALFORMED[name]
    _set(monkeypatch, {**PROFILE_ENVS[profile], "APP_SETTINGS_ENCRYPTION_KEY": value})

    with pytest.raises(ValidationError, match="settings_encryption_key") as caught:
        get_settings()

    if len(value) >= 8:  # 값 자체가 메시지에 들어 있지 않다(짧은 값은 우연히 겹칠 수 있다)
        assert value not in str(caught.value)


def test_product_rejects_example_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(
        monkeypatch,
        {**PRODUCT_ENV, "APP_SETTINGS_ENCRYPTION_KEY": EXAMPLE_SETTINGS_ENCRYPTION_KEY},
    )

    with pytest.raises(ValidationError, match="settings_encryption_key") as caught:
        get_settings()

    assert EXAMPLE_SETTINGS_ENCRYPTION_KEY not in str(caught.value)


@pytest.mark.parametrize("profile", ["local", "dev"])
def test_local_and_dev_accept_the_example_key(
    monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    _set(
        monkeypatch,
        {**PROFILE_ENVS[profile], "APP_SETTINGS_ENCRYPTION_KEY": EXAMPLE_SETTINGS_ENCRYPTION_KEY},
    )

    assert get_settings().settings_encryption_key.get_secret_value() == (
        EXAMPLE_SETTINGS_ENCRYPTION_KEY
    )


def test_the_example_key_is_a_well_formed_fernet_key() -> None:
    decoded = base64.urlsafe_b64decode(EXAMPLE_SETTINGS_ENCRYPTION_KEY.encode())

    assert len(decoded) == FERNET_KEY_BYTES


def test_example_key_constant_matches_env_example() -> None:
    """product 거부 예시 키와 `.env.example`에 적힌 키가 같다(복사한 채 배포하는 사고 방지)."""
    text = (BACKEND / ".env.example").read_text(encoding="utf-8")

    match = re.search(r"^APP_SETTINGS_ENCRYPTION_KEY=(\S+)\s*$", text, flags=re.MULTILINE)

    assert match is not None, ".env.example에 APP_SETTINGS_ENCRYPTION_KEY가 있어야 한다"
    assert match.group(1) == EXAMPLE_SETTINGS_ENCRYPTION_KEY


def _same_bytes_other_text(key: str) -> str:
    """같은 32바이트로 디코드되지만 마지막 글자(미사용 하위 비트)만 다른 유효한 URL-safe 표기."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    body = key.rstrip("=")
    index = alphabet.index(body[-1])
    group = index - index % 4
    other = alphabet[group + (index % 4 + 1) % 4]
    return body[:-1] + other + key[len(body) :]


def test_product_compares_the_example_key_by_decoded_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    variant = _same_bytes_other_text(EXAMPLE_SETTINGS_ENCRYPTION_KEY)
    assert variant != EXAMPLE_SETTINGS_ENCRYPTION_KEY
    assert base64.urlsafe_b64decode(variant) == base64.urlsafe_b64decode(
        EXAMPLE_SETTINGS_ENCRYPTION_KEY
    )
    _set(monkeypatch, {**PRODUCT_ENV, "APP_SETTINGS_ENCRYPTION_KEY": variant})

    with pytest.raises(ValidationError, match="settings_encryption_key") as caught:
        get_settings()

    assert variant not in str(caught.value)
    assert EXAMPLE_SETTINGS_ENCRYPTION_KEY not in str(caught.value)


def test_example_key_with_a_stray_character_is_a_format_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = EXAMPLE_SETTINGS_ENCRYPTION_KEY[:10] + "." + EXAMPLE_SETTINGS_ENCRYPTION_KEY[10:]
    _set(monkeypatch, {**PRODUCT_ENV, "APP_SETTINGS_ENCRYPTION_KEY": broken})

    with pytest.raises(ValidationError, match="Fernet 키 형식"):
        get_settings()
