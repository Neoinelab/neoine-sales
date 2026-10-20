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


def test_redis_is_not_required() -> None:
    assert get_settings().redis_url is None


def test_redis_url_is_parsed_when_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_REDIS_URL", "redis://localhost:6379/0")

    redis_url = get_settings().redis_url

    assert redis_url is not None
    assert redis_url.host == "localhost"


def test_invalid_redis_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_REDIS_URL", "not-a-redis-url")

    with pytest.raises(ValidationError, match="redis_url"):
        get_settings()


def test_local_enables_dev_login_by_default() -> None:
    assert get_settings().dev_login_enabled is True


def test_dev_login_is_allowed_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, {"APP_PROFILE": "dev", "APP_DEV_LOGIN_ENABLED": "true"})

    assert get_settings().dev_login_enabled is True


def test_dev_enables_dev_login_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PROFILE", "dev")

    assert get_settings().dev_login_enabled is True


def test_dev_login_is_forbidden_in_product(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, {**PRODUCT_ENV, "APP_DEV_LOGIN_ENABLED": "true"})

    with pytest.raises(ValidationError, match="dev_login"):
        get_settings()


# 예전 OIDC 배포 환경의 잔여 변수. 값이 JSON이 아니어도 무시해야 한다(CFG-2).
STALE_OIDC_ENV = {
    "APP_OIDC_ISSUER": "https://adfs.example.com/adfs",
    "APP_OIDC_CLIENT_ID": "neoine-sales",
    "APP_OIDC_CLIENT_SECRET": "client-secret-value",
    "APP_OIDC_REDIRECT_URI": "https://sales.example.com/api/v1/auth/callback",
    "APP_OIDC_ADMIN_GROUPS": "not-json-at-all",
    "APP_OIDC_SALES_GROUPS": "[broken",
    "APP_OIDC_SCOPES": "{",
}


def test_settings_have_no_oidc_fields_or_properties() -> None:
    settings = get_settings()

    assert not [name for name in type(settings).model_fields if name.startswith("oidc")]
    assert not hasattr(settings, "oidc_enabled")


@pytest.mark.parametrize("profile", ["local", "dev", "product"])
def test_oidc_variables_left_in_the_environment_are_ignored(
    monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    _set(monkeypatch, {**PRODUCT_ENV, "APP_PROFILE": profile, **STALE_OIDC_ENV})

    settings = get_settings()

    assert settings.profile.value == profile
    assert not hasattr(settings, "oidc_issuer")
    assert "client-secret-value" not in repr(settings)


def test_oidc_variables_in_a_dotenv_file_are_ignored(tmp_path: Path) -> None:
    lines = [f"{key}={value}" for key, value in STALE_OIDC_ENV.items()]
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    settings = get_settings()

    assert isinstance(settings, LocalSettings)


def test_product_starts_without_any_login_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, PRODUCT_ENV)

    settings = get_settings()

    assert settings.profile is Profile.PRODUCT
    assert settings.dev_login_enabled is False


def test_local_without_dev_login_starts_without_any_login_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_DEV_LOGIN_ENABLED", "false")

    settings = get_settings()

    assert settings.dev_login_enabled is False


def test_session_ttl_default_and_secrets_stay_hidden() -> None:
    settings = get_settings()

    assert settings.session_ttl_hours == 8
    assert JWT_SECRET not in repr(settings)
