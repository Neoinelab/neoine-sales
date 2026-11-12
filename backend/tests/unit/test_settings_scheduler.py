"""앱 내 스케줄러 설정.

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
    """local 프로파일은 스케줄러가 기본으로 꺼져 있다

    테스트 코드: FC-046
    """
    # when: local 설정을 읽는다
    settings = get_settings()

    # then: scheduler_enabled가 False다
    assert isinstance(settings, LocalSettings)
    assert settings.scheduler_enabled is False


def test_scheduler_is_enabled_by_default_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """dev 프로파일은 스케줄러가 기본으로 켜져 있다

    테스트 코드: FC-046
    """
    # given: APP_PROFILE=dev
    monkeypatch.setenv("APP_PROFILE", "dev")

    # when: 설정을 읽는다
    settings = get_settings()

    # then: scheduler_enabled가 True다
    assert isinstance(settings, DevSettings)
    assert settings.scheduler_enabled is True


def test_scheduler_is_enabled_by_default_in_product(monkeypatch: pytest.MonkeyPatch) -> None:
    """product 프로파일은 스케줄러가 기본으로 켜져 있다

    테스트 코드: FC-046
    """
    # given: product 프로파일 환경
    for key, value in PRODUCT_ENV.items():
        monkeypatch.setenv(key, value)

    # when: 설정을 읽는다
    settings = get_settings()

    # then: scheduler_enabled가 True다
    assert isinstance(settings, ProductSettings)
    assert settings.scheduler_enabled is True


def test_interval_defaults_to_600_seconds() -> None:
    """확인 간격의 기본값은 600초다

    테스트 코드: FC-046
    """
    # when: 설정을 읽는다
    seconds = get_settings().forecast_snapshot_check_interval_seconds
    # then: 확인 간격이 600초다
    assert seconds == DEFAULT_INTERVAL


@pytest.mark.parametrize("seconds", [30, 31, 3599, 3600])
def test_interval_inside_the_bounds_is_accepted(
    monkeypatch: pytest.MonkeyPatch, seconds: int
) -> None:
    """30~3600초 안의 간격은 받아들인다

    테스트 코드: FC-046
    """
    # given: 범위 안의 간격 환경변수
    monkeypatch.setenv(INTERVAL, str(seconds))

    # when: 설정을 읽는다
    interval = get_settings().forecast_snapshot_check_interval_seconds
    # then: 간격이 그 값이다
    assert interval == seconds


@pytest.mark.parametrize("seconds", ["29", "3601", "0", "-1"])
def test_interval_outside_the_bounds_is_rejected(
    monkeypatch: pytest.MonkeyPatch, seconds: str
) -> None:
    """30~3600초 밖의 간격은 설정 오류다

    테스트 코드: FC-046
    """
    # given: 범위 밖의 간격 환경변수
    monkeypatch.setenv(INTERVAL, seconds)

    # when·then: 설정을 읽으면 ValidationError다
    with pytest.raises(ValidationError):
        get_settings()


def test_scheduler_settings_are_read_from_app_prefixed_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """스케줄러 설정은 APP_ 접두사 환경변수로 읽는다

    테스트 코드: FC-046
    """
    # given: 켜짐과 간격 120초 환경변수
    monkeypatch.setenv("APP_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv(INTERVAL, "120")

    # when: 설정을 읽는다
    settings = get_settings()

    # then: 켜짐이고 간격이 120초다
    assert settings.scheduler_enabled is True
    assert settings.forecast_snapshot_check_interval_seconds == 120


def test_dev_scheduler_can_be_turned_off_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """dev에서도 환경변수로 스케줄러를 끌 수 있다

    테스트 코드: FC-046
    """
    # given: dev 프로파일에 APP_SCHEDULER_ENABLED=false
    monkeypatch.setenv("APP_PROFILE", "dev")
    monkeypatch.setenv("APP_SCHEDULER_ENABLED", "false")

    # when: 설정을 읽는다
    enabled = get_settings().scheduler_enabled
    # then: 꺼짐이다
    assert enabled is False
