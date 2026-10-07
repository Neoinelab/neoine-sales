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
    jwt_secret: SecretStr  # 로그인 state 서명 키(기존 환경변수명 유지)
    session_ttl_hours: int = Field(default=8, ge=1)

    # 로그인: OIDC(AD FS, Entra ID 등). 역할은 IdP 그룹 이름을 앱 역할(admin/sales)로 매핑한다
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_redirect_uri: str | None = None
    oidc_scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    oidc_groups_claim: str = "groups"
    oidc_admin_groups: list[str] = Field(default_factory=list)
    oidc_sales_groups: list[str] = Field(default_factory=list)
    dev_login_enabled: bool = False  # IdP 없이 로그인하는 개발용 기능. local에서만 켤 수 있다

    # 데이터 저장소
    database_url: PostgresDsn
    db_pool_size: int = Field(default=10, ge=1)
    db_echo: bool = False
    redis_url: RedisDsn | None = None  # 현재 미사용. 큐·캐시를 도입할 때 필수로 바꾼다

    # 관측성
    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    otel_exporter_endpoint: str | None = None

    @property
    def oidc_enabled(self) -> bool:
        return all(
            (self.oidc_issuer, self.oidc_client_id, self.oidc_client_secret, self.oidc_redirect_uri)
        )

    @model_validator(mode="after")
    def _check_login_configuration(self) -> Self:
        if self.dev_login_enabled and self.profile is not Profile.LOCAL:
            raise ValueError("dev_login_enabled는 local 프로파일에서만 켤 수 있습니다")
        if not self.dev_login_enabled and not self.oidc_enabled:
            raise ValueError(
                "OIDC 설정(oidc_issuer, oidc_client_id, oidc_client_secret, oidc_redirect_uri)이 "
                "필요합니다"
            )
        if not self.dev_login_enabled and not (self.oidc_admin_groups or self.oidc_sales_groups):
            raise ValueError(
                "OIDC 그룹(oidc_admin_groups, oidc_sales_groups)이 하나 이상 필요합니다"
            )
        return self
