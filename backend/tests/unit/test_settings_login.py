"""T-S7: 로그인 시도 제한 설정(APP_LOGIN_*, CFG-3). 선택 항목, 기본값 있음, 범위 검증."""

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.config.profiles import LocalSettings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

FIELDS = {
    "APP_LOGIN_MAX_FAILURES_PER_ACCOUNT": ("login_max_failures_per_account", 5),
    "APP_LOGIN_MAX_FAILURES_PER_IP": ("login_max_failures_per_ip", 30),
    "APP_LOGIN_FAILURE_WINDOW_MINUTES": ("login_failure_window_minutes", 15),
    "APP_LOGIN_LOCK_MINUTES": ("login_lock_minutes", 15),
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    for key in [k for k in os.environ if k.startswith("APP_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/app")
    monkeypatch.setenv("APP_JWT_SECRET", "x" * 40)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_login_throttle_defaults_match_the_plan() -> None:
    settings = get_settings()

    assert isinstance(settings, LocalSettings)
    assert settings.login_max_failures_per_account == 5
    assert settings.login_max_failures_per_ip == 30
    assert settings.login_failure_window_minutes == 15
    assert settings.login_lock_minutes == 15


@pytest.mark.parametrize("variable", list(FIELDS))
def test_login_throttle_values_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "7")

    settings = get_settings()

    assert getattr(settings, FIELDS[variable][0]) == 7


@pytest.mark.parametrize("variable", list(FIELDS))
@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_login_throttle_values_reject_out_of_range_input(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        get_settings()


@pytest.mark.parametrize("variable", list(FIELDS))
def test_login_throttle_values_accept_the_minimum(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "1")

    assert getattr(get_settings(), FIELDS[variable][0]) == 1


def test_no_ldap_connection_variables_exist_on_settings() -> None:
    names = set(get_settings().model_dump())

    assert not {n for n in names if n.startswith("ldap")}
