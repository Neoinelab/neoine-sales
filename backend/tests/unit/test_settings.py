import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.config import Profile, get_settings
from app.config.profiles import DevSettings, LocalSettings, ProductSettings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

JWT_SECRET = "x" * 40
BASE_ENV = {
    "APP_DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/app",
    "APP_REDIS_URL": "redis://localhost:6379/0",
    "APP_JWT_SECRET": JWT_SECRET,
}
PRODUCT_ENV = {
    "APP_PROFILE": "product",
    "APP_SENTRY_DSN": "https://key@sentry.internal.example.com/1",
    "APP_CORS_ALLOWED_ORIGINS": '["https://sales.internal.example.com"]',
}
PRODUCT_WORKERS = 4


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """실제 환경변수와 .env 파일의 영향을 받지 않도록 격리한다."""
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


def test_defaults_to_local_profile_when_profile_is_not_set() -> None:
    settings = get_settings()

    assert isinstance(settings, LocalSettings)
    assert settings.profile is Profile.LOCAL
    assert settings.debug is True
    assert settings.log_format == "console"


def test_dev_profile_uses_json_logs_and_debug_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PROFILE", "dev")

    settings = get_settings()

    assert isinstance(settings, DevSettings)
    assert settings.debug is False
    assert settings.log_format == "json"


def test_product_accepts_valid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, PRODUCT_ENV)

    settings = get_settings()

    assert isinstance(settings, ProductSettings)
    assert settings.enable_docs is False
    assert settings.workers == PRODUCT_WORKERS


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"APP_DEBUG": "true"}, "debug"),
        ({"APP_ENABLE_DOCS": "true"}, "enable_docs"),
        ({"APP_COOKIE_SECURE": "false"}, "cookie_secure"),
        ({"APP_CORS_ALLOWED_ORIGINS": '["*"]'}, "CORS"),
        ({"APP_JWT_SECRET": "short"}, "jwt_secret"),
    ],
)
def test_product_rejects_unsafe_settings(
    monkeypatch: pytest.MonkeyPatch, override: dict[str, str], message: str
) -> None:
    _set(monkeypatch, {**PRODUCT_ENV, **override})

    with pytest.raises(ValidationError, match=message):
        get_settings()


def test_product_requires_sentry_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, PRODUCT_ENV)
    monkeypatch.delenv("APP_SENTRY_DSN")

    with pytest.raises(ValidationError, match="sentry_dsn"):
        get_settings()


def test_unknown_profile_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PROFILE", "prod")

    with pytest.raises(ValidationError, match="profile"):
        get_settings()


def test_profile_can_be_read_from_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("APP_PROFILE=dev\n", encoding="utf-8")

    settings = get_settings()

    assert isinstance(settings, DevSettings)


def test_missing_required_variable_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_JWT_SECRET")

    with pytest.raises(ValidationError, match="jwt_secret"):
        get_settings()


def test_secret_values_are_not_exposed_in_repr() -> None:
    assert JWT_SECRET not in repr(get_settings())
