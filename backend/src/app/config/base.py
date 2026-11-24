"""프로파일 공통 설정. 값은 APP_ 접두어 환경변수에서 읽는다."""

import base64
import binascii
import re
from enum import StrEnum
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

FERNET_KEY_BYTES = 32
_URLSAFE_B64 = re.compile(r"[A-Za-z0-9_-]+={0,2}")
_DOMAIN_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_DOMAIN = re.compile(rf"{_DOMAIN_LABEL}(?:\.{_DOMAIN_LABEL})*")
DOMAIN_MAX_LENGTH = 253


def decode_fernet_key(text: str) -> bytes | None:
    """URL-safe base64 알파벳(`A-Za-z0-9_-`, 끝 `=` 패딩)만 허용해 풀고, 형식 오류면 None이다."""
    if _URLSAFE_B64.fullmatch(text) is None:
        return None
    try:
        return base64.urlsafe_b64decode(text.encode("ascii"))
    except binascii.Error, ValueError:
        return None


type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
type LogFormat = Literal["console", "json"]


class Profile(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PRODUCT = "product"


class Settings(BaseSettings):
    """모든 프로파일이 공유하는 필드. 프로파일별 기본값 차이는 profiles.py에서 정의한다."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,  # 검증 오류에 비밀 값이 나오지 않게 한다
    )

    profile: Profile
    debug: bool = False
    enable_docs: bool = False
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "json"
    workers: int = Field(default=2, ge=1)

    # 앱 내 스케줄러(Forecast 월말 스냅숏 확인): 워커마다 돌고 advisory lock으로 한 곳만 작업한다
    scheduler_enabled: bool = True
    forecast_snapshot_check_interval_seconds: int = Field(default=600, ge=30, le=3600)

    # 웹/보안 (cors_allowed_origins는 환경변수에서 JSON 배열 문자열로 전달)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    cookie_secure: bool = True
    jwt_secret: SecretStr  # 로그인 실패 카운터 키(HMAC) 서명 키(기존 환경변수명 유지)
    session_ttl_hours: int = Field(default=8, ge=1)
    # AD 바인드 비밀번호 암호화 키(Fernet: URL-safe base64 32바이트). jwt_secret과 별개
    settings_encryption_key: SecretStr

    # AD 사용자 비밀번호 바인드를 <아이디>@<도메인>으로 하는 도메인(선택, 없으면 찾은 DN으로 바인드)
    ad_login_domain: str | None = None

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

    @field_validator("settings_encryption_key")
    @classmethod
    def _check_encryption_key(cls, value: SecretStr) -> SecretStr:
        decoded = decode_fernet_key(value.get_secret_value())
        if decoded is None or len(decoded) != FERNET_KEY_BYTES:
            raise ValueError("Fernet 키 형식(URL-safe base64로 인코딩한 32바이트)이어야 합니다")
        return value

    @field_validator("ad_login_domain")
    @classmethod
    def _check_ad_login_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().lower()
        if not text:
            return None
        if len(text) > DOMAIN_MAX_LENGTH or _DOMAIN.fullmatch(text) is None:
            raise ValueError("ad_login_domain은 도메인 형식(예: neoine.co.kr)이어야 합니다")
        return text
