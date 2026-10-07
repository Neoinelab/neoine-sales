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
OIDC_ENV = {
    "APP_OIDC_ISSUER": "https://adfs.example.com/adfs",
    "APP_OIDC_CLIENT_ID": "neoine-sales",
    "APP_OIDC_CLIENT_SECRET": "client-secret-value",
    "APP_OIDC_REDIRECT_URI": "https://sales.example.com/api/v1/auth/callback",
    "APP_OIDC_ADMIN_GROUPS": '["Sales-Admins"]',
    "APP_OIDC_SALES_GROUPS": '["Sales-Team"]',
}
BASE_ENV = {
    "APP_DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/app",
    "APP_JWT_SECRET": JWT_SECRET,
    **OIDC_ENV,
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


def test_dev_login_is_forbidden_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, {"APP_PROFILE": "dev", "APP_DEV_LOGIN_ENABLED": "true"})

    with pytest.raises(ValidationError, match="dev_login"):
        get_settings()


def test_dev_login_is_forbidden_in_product(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, {**PRODUCT_ENV, "APP_DEV_LOGIN_ENABLED": "true"})

    with pytest.raises(ValidationError, match="dev_login"):
        get_settings()


@pytest.mark.parametrize("profile", ["dev", "product"])
@pytest.mark.parametrize("missing", [k for k in sorted(OIDC_ENV) if "GROUPS" not in k])
def test_oidc_settings_are_required_outside_local(
    monkeypatch: pytest.MonkeyPatch, profile: str, missing: str
) -> None:
    _set(monkeypatch, {**PRODUCT_ENV, "APP_PROFILE": profile})
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError, match="OIDC"):
        get_settings()


def test_local_without_dev_login_requires_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DEV_LOGIN_ENABLED", "false")
    monkeypatch.delenv("APP_OIDC_ISSUER")

    with pytest.raises(ValidationError, match="OIDC"):
        get_settings()


def test_local_with_dev_login_does_not_need_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in OIDC_ENV:
        monkeypatch.delenv(key)

    settings = get_settings()

    assert settings.oidc_enabled is False
    assert settings.dev_login_enabled is True


def test_oidc_group_lists_and_defaults() -> None:
    settings = get_settings()

    assert settings.oidc_enabled is True
    assert settings.oidc_admin_groups == ["Sales-Admins"]
    assert settings.oidc_sales_groups == ["Sales-Team"]
    assert settings.oidc_groups_claim == "groups"
    assert settings.session_ttl_hours == 8
    assert "client-secret-value" not in repr(settings)


@pytest.mark.parametrize("profile", ["dev", "product"])
def test_at_least_one_oidc_group_is_required_outside_local(
    monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    _set(monkeypatch, {**PRODUCT_ENV, "APP_PROFILE": profile})
    monkeypatch.delenv("APP_OIDC_ADMIN_GROUPS")
    monkeypatch.delenv("APP_OIDC_SALES_GROUPS")

    with pytest.raises(ValidationError, match="OIDC 그룹"):
        get_settings()
