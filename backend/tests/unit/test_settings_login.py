"""T-S7: 로그인 시도 제한 설정(APP_LOGIN_*, CFG-3). 선택 항목, 기본값 있음, 범위 검증."""

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.config.profiles import LocalSettings
from tests.support.crypto_keys import TEST_FERNET_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

FIELDS = {
    "APP_LOGIN_MAX_FAILURES_PER_ACCOUNT": ("login_max_failures_per_account", 10),
    "APP_LOGIN_MAX_FAILURES_PER_IP": ("login_max_failures_per_ip", 30),
    "APP_LOGIN_FAILURE_WINDOW_MINUTES": ("login_failure_window_minutes", 15),
    "APP_LOGIN_LOCK_MINUTES": ("login_lock_minutes", 15),
    "APP_LOGIN_ACCOUNT_FIRST_LOCK_MINUTES": ("login_account_first_lock_minutes", 5),
    "APP_LOGIN_ACCOUNT_REPEAT_LOCK_MINUTES": ("login_account_repeat_lock_minutes", 60),
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    for key in [k for k in os.environ if k.startswith("APP_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/app")
    monkeypatch.setenv("APP_JWT_SECRET", "x" * 40)
    monkeypatch.setenv("APP_SETTINGS_ENCRYPTION_KEY", TEST_FERNET_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_login_throttle_defaults_match_the_plan() -> None:
    # when: 설정을 읽으면 (전제: 시도 제한 환경변수를 설정하지 않았다)
    settings = get_settings()

    assert isinstance(settings, LocalSettings)
    for field, expected in FIELDS.values():
        assert getattr(settings, field) == expected


@pytest.mark.parametrize("variable", list(FIELDS))
def test_login_throttle_values_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    """시도 제한 값을 환경변수로 바꿀 수 있다."""
    # when: 시도 제한 변수에 7을 넣고 설정을 읽으면
    monkeypatch.setenv(variable, "7")

    settings = get_settings()

    # then: 7이 쓰인다
    assert getattr(settings, FIELDS[variable][0]) == 7


@pytest.mark.parametrize("variable", list(FIELDS))
@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_login_throttle_values_reject_out_of_range_input(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    """시도 제한 값이 1 미만이거나 숫자가 아니면 거부된다.

    테스트 코드: AU-052
    """
    # when: 각 시도 제한 변수에 0·-1·abc·1.5를 넣고 설정을 읽으면
    monkeypatch.setenv(variable, value)

    # then: 검증 오류다
    with pytest.raises(ValidationError):
        get_settings()


@pytest.mark.parametrize("variable", list(FIELDS))
def test_login_throttle_values_accept_the_minimum(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    """시도 제한 값은 1까지 허용된다.

    테스트 코드: AU-052
    """
    # when: 각 시도 제한 변수에 1을 넣고 설정을 읽으면
    monkeypatch.setenv(variable, "1")

    # then: 그 값이 그대로 쓰인다
    assert getattr(get_settings(), FIELDS[variable][0]) == 1


def test_no_ldap_connection_variables_exist_on_settings() -> None:
    """Settings에는 LDAP 접속 변수가 없다."""
    # when: Settings 필드 이름을 모은다
    names = set(get_settings().model_dump())

    # then: ldap으로 시작하는 이름이 없다
    assert not {n for n in names if n.startswith("ldap")}
