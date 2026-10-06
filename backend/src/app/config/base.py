"""프로파일 공통 설정. 값은 APP_ 접두어 환경변수에서 읽는다."""

from enum import StrEnum
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
type LogFormat = Literal["console", "json"]


class Profile(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PRODUCT = "product"


class Settings(BaseSettings):
    """모든 프로파일이 공유하는 필드. 프로파일별 기본값 차이는 profiles.py에서 정의한다."""

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    profile: Profile
    debug: bool = False
    enable_docs: bool = False
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "json"
    workers: int = Field(default=2, ge=1)

    # 웹/보안 (cors_allowed_origins는 환경변수에서 JSON 배열 문자열로 전달)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    cookie_secure: bool = True
    jwt_secret: SecretStr
    access_token_ttl_minutes: int = Field(default=15, ge=1)
    refresh_token_ttl_days: int = Field(default=7, ge=1)

    # 데이터 저장소
    database_url: PostgresDsn
    db_pool_size: int = Field(default=10, ge=1)
    db_echo: bool = False
    redis_url: RedisDsn

    # 관측성
    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    otel_exporter_endpoint: str | None = None
