"""앱 내 스케줄러 설정(docker-compose 계획 D9, AC16·AC21).

`APP_SCHEDULER_ENABLED`: LocalSettings는 꺼짐, Dev·Product는 켜짐.
`APP_FORECAST_SNAPSHOT_CHECK_INTERVAL_SECONDS`: 기본 600, 30~3600.
"""

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.config.profiles import DevSettings, LocalSettings, ProductSettings
from tests.support.crypto_keys import TEST_FERNET_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

BASE_ENV = {
    "APP_DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/app",
    "APP_JWT_SECRET": "x" * 40,
    "APP_SETTINGS_ENCRYPTION_KEY": TEST_FERNET_KEY,
}
PRODUCT_ENV = {
    "APP_PROFILE": "product",
    "APP_SENTRY_DSN": "https://key@sentry.internal.example.com/1",
    "APP_CORS_ALLOWED_ORIGINS": '["https://sales.internal.example.com"]',
}
INTERVAL = "APP_FORECAST_SNAPSHOT_CHECK_INTERVAL_SECONDS"
DEFAULT_INTERVAL = 600


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


def test_scheduler_is_disabled_by_default_in_local() -> None:
    settings = get_settings()

    assert isinstance(settings, LocalSettings)
    assert settings.scheduler_enabled is False


def test_scheduler_is_enabled_by_default_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PROFILE", "dev")

    settings = get_settings()

    assert isinstance(settings, DevSettings)
    assert settings.scheduler_enabled is True


def test_scheduler_is_enabled_by_default_in_product(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in PRODUCT_ENV.items():
        monkeypatch.setenv(key, value)

    settings = get_settings()

    assert isinstance(settings, ProductSettings)
    assert settings.scheduler_enabled is True


def test_interval_defaults_to_600_seconds() -> None:
    assert get_settings().forecast_snapshot_check_interval_seconds == DEFAULT_INTERVAL


@pytest.mark.parametrize("seconds", [30, 31, 3599, 3600])
def test_interval_inside_the_bounds_is_accepted(
    monkeypatch: pytest.MonkeyPatch, seconds: int
) -> None:
    monkeypatch.setenv(INTERVAL, str(seconds))

    assert get_settings().forecast_snapshot_check_interval_seconds == seconds


@pytest.mark.parametrize("seconds", ["29", "3601", "0", "-1"])
def test_interval_outside_the_bounds_is_rejected(
    monkeypatch: pytest.MonkeyPatch, seconds: str
) -> None:
    monkeypatch.setenv(INTERVAL, seconds)

    with pytest.raises(ValidationError):
        get_settings()


def test_scheduler_settings_are_read_from_app_prefixed_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv(INTERVAL, "120")

    settings = get_settings()

    assert settings.scheduler_enabled is True
    assert settings.forecast_snapshot_check_interval_seconds == 120


def test_dev_scheduler_can_be_turned_off_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PROFILE", "dev")
    monkeypatch.setenv("APP_SCHEDULER_ENABLED", "false")

    assert get_settings().scheduler_enabled is False
