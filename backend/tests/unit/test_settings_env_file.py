"""APP_ENV_FILE로 읽을 env 파일을 고르는 규칙(프로파일 선택 실행)."""

import os
from typing import TYPE_CHECKING

import pytest

from app.config import Profile, get_settings
from app.config.profiles import DevSettings, LocalSettings

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
    settings = get_settings()

    assert isinstance(settings, LocalSettings)
    assert settings.database_url.hosts()[0]["host"] == DEFAULT_HOST


@pytest.mark.usefixtures("env_files")
def test_env_file_variable_selects_the_file_and_ignores_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV_FILE", ".env.dev")

    settings = get_settings()

    assert isinstance(settings, DevSettings)
    assert settings.profile is Profile.DEV
    assert settings.database_url.hosts()[0]["host"] == DEV_HOST


@pytest.mark.usefixtures("env_files")
def test_missing_env_file_fails_with_its_path_in_the_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV_FILE", ".env.missing")

    with pytest.raises(FileNotFoundError) as excinfo:
        get_settings()

    message = str(excinfo.value)
    assert ".env.missing" in message
    assert DEFAULT_HOST not in message
    assert JWT_SECRET not in message


def test_profile_environment_variable_wins_over_env_file_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env.dev").write_text("APP_PROFILE=local\n" + _url(DEV_HOST), encoding="utf-8")
    monkeypatch.setenv("APP_ENV_FILE", ".env.dev")
    monkeypatch.setenv("APP_PROFILE", "dev")

    settings = get_settings()

    assert isinstance(settings, DevSettings)
    assert settings.database_url.hosts()[0]["host"] == DEV_HOST
