"""APP_ENV_FILE로 읽을 env 파일을 고르는 규칙(PL-R24, PL-042)."""

import os
from typing import TYPE_CHECKING

import pytest

from app.config import Profile, get_settings
from app.config.profiles import DevSettings, LocalSettings
from tests.support.crypto_keys import TEST_FERNET_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

JWT_SECRET = "x" * 40
DEFAULT_HOST = "default-db.example.test"
DEV_HOST = "dev-db.example.test"


def _url(host: str) -> str:
    return f"APP_DATABASE_URL=postgresql+asyncpg://u:p@{host}:5432/app\n"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """실제 환경변수와 backend/.env의 영향을 받지 않도록 tmp 디렉터리로 격리한다.

    APP_DATABASE_URL은 파일에서 읽는 값을 검증하려고 설정하지 않는다.
    """
    monkeypatch.chdir(tmp_path)
    for key in [k for k in os.environ if k.startswith("APP_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("APP_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("APP_SETTINGS_ENCRYPTION_KEY", TEST_FERNET_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def env_files(tmp_path: Path) -> None:
    """같은 디렉터리에 .env(local)와 .env.dev(dev) 더미 파일을 만든다."""
    (tmp_path / ".env").write_text("APP_PROFILE=local\n" + _url(DEFAULT_HOST), encoding="utf-8")
    (tmp_path / ".env.dev").write_text("APP_PROFILE=dev\n" + _url(DEV_HOST), encoding="utf-8")


@pytest.mark.usefixtures("env_files")
def test_dotenv_is_read_when_env_file_is_not_set() -> None:
    """APP_ENV_FILE가 없으면 .env를 읽는다.

    테스트 코드: PL-042
    """
    # when: 설정을 읽는다 (전제: .env(local)와 .env.dev(dev)가 있고 APP_ENV_FILE는 없다)
    settings = get_settings()
    # then: .env의 값을 읽는다
    assert isinstance(settings, LocalSettings)
    assert settings.database_url.hosts()[0]["host"] == DEFAULT_HOST


@pytest.mark.usefixtures("env_files")
def test_env_file_variable_selects_the_file_and_ignores_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """APP_ENV_FILE로 지정한 파일만 읽고 .env는 무시한다.

    테스트 코드: PL-042
    """
    # given: APP_ENV_FILE=.env.dev
    monkeypatch.setenv("APP_ENV_FILE", ".env.dev")
    # when: 설정을 읽는다
    settings = get_settings()
    # then: .env.dev의 값(dev 프로파일, dev 호스트)만 쓴다
    assert isinstance(settings, DevSettings)
    assert settings.profile is Profile.DEV
    assert settings.database_url.hosts()[0]["host"] == DEV_HOST


@pytest.mark.usefixtures("env_files")
def test_missing_env_file_fails_with_its_path_in_the_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """지정한 env 파일이 없으면 경로를 알리며 실패하고 다른 값은 싣지 않는다.

    테스트 코드: PL-042
    """
    # given: 없는 파일을 APP_ENV_FILE로 지정
    monkeypatch.setenv("APP_ENV_FILE", ".env.missing")
    # when: 설정을 읽는다
    with pytest.raises(FileNotFoundError) as excinfo:
        get_settings()
    # then: 안내 문구와 경로가 있고 다른 파일의 값이나 비밀은 없다
    message = str(excinfo.value)
    assert "APP_ENV_FILE로 지정한 env 파일이 없습니다" in message
    assert ".env.missing" in message
    assert DEFAULT_HOST not in message
    assert JWT_SECRET not in message


def test_profile_environment_variable_wins_over_env_file_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """환경변수의 프로파일이 env 파일의 프로파일보다 우선한다.

    테스트 코드: PL-042
    """
    # given: 파일에는 APP_PROFILE=local, 환경변수에는 dev
    (tmp_path / ".env.dev").write_text("APP_PROFILE=local\n" + _url(DEV_HOST), encoding="utf-8")
    monkeypatch.setenv("APP_ENV_FILE", ".env.dev")
    monkeypatch.setenv("APP_PROFILE", "dev")
    # when: 설정을 읽는다
    settings = get_settings()
    # then: 환경변수의 프로파일(dev)을 쓴다
    assert isinstance(settings, DevSettings)
    assert settings.database_url.hosts()[0]["host"] == DEV_HOST
