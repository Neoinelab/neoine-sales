"""프로파일 공통 설정. 값은 APP_ 접두어 환경변수에서 읽는다."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, model_validator
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
    jwt_secret: SecretStr  # 로그인 실패 카운터 키(HMAC) 서명 키(기존 환경변수명 유지)
    session_ttl_hours: int = Field(default=8, ge=1)

    # 로그인: AD(LDAP) 서버는 화면에서 등록하므로 환경변수가 없다
    dev_login_enabled: bool = False  # IdP 없이 로그인하는 개발용 기능. product에서는 켤 수 없다

    # 로그인 시도 제한(계정별·IP별 실패 횟수, 집계 창, 잠금 시간)
    login_max_failures_per_account: int = Field(default=5, ge=1)
    login_max_failures_per_ip: int = Field(default=30, ge=1)
    login_failure_window_minutes: int = Field(default=15, ge=1)
    login_lock_minutes: int = Field(default=15, ge=1)

    # 데이터 저장소
    database_url: PostgresDsn
    db_pool_size: int = Field(default=10, ge=1)
    db_echo: bool = False
    redis_url: RedisDsn | None = None  # 현재 미사용. 큐·캐시를 도입할 때 필수로 바꾼다

    # 관측성
    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    otel_exporter_endpoint: str | None = None

    @model_validator(mode="after")
    def _check_login_configuration(self) -> Self:
        if self.dev_login_enabled and self.profile is Profile.PRODUCT:
            raise ValueError("dev_login_enabled는 product 프로파일에서 켤 수 없습니다")
        return self
