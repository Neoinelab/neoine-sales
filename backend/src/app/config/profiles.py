"""프로파일(local/dev/product)별 기본 동작 차이. 환경마다 다른 '값'은 환경변수로 주입한다."""

import base64
from typing import Self

from pydantic import model_validator

from app.config.base import LogFormat, LogLevel, Profile, Settings, decode_fernet_key

MIN_PRODUCT_JWT_SECRET_LENGTH = 32
# backend/.env.example에 적힌 예시 키. 공개된 값이므로 product에서는 거부한다.
EXAMPLE_SETTINGS_ENCRYPTION_KEY = "ZXhhbXBsZS1rZXktbm90LWZvci1wcm9kdWN0aW9uISE="
_EXAMPLE_KEY_BYTES = base64.urlsafe_b64decode(EXAMPLE_SETTINGS_ENCRYPTION_KEY)


class LocalSettings(Settings):
    profile: Profile = Profile.LOCAL
    debug: bool = True
    enable_docs: bool = True
    log_level: LogLevel = "DEBUG"
    log_format: LogFormat = "console"
    cookie_secure: bool = False  # 로컬은 http
    dev_login_enabled: bool = True  # 로컬에서는 IdP 없이 개발용 로그인을 쓴다
    db_pool_size: int = 5
    db_echo: bool = True
    workers: int = 1


class DevSettings(Settings):
    profile: Profile = Profile.DEV
    enable_docs: bool = True
    log_level: LogLevel = "DEBUG"
    dev_login_enabled: bool = True  # 사용자 결정 2026-10-20: dev도 개발용 로그인을 유지한다
    sentry_traces_sample_rate: float = 1.0


class ProductSettings(Settings):
    profile: Profile = Profile.PRODUCT
    workers: int = 4
    sentry_traces_sample_rate: float = 0.1

    @model_validator(mode="after")
    def _check_safe_for_product(self) -> Self:
        problems: list[str] = []
        if self.debug or self.enable_docs or self.db_echo:
            problems.append("debug/enable_docs/db_echo는 product에서 꺼야 합니다")
        if not self.cookie_secure:
            problems.append("cookie_secure는 true여야 합니다")
        if "*" in self.cors_allowed_origins:
            problems.append("CORS에 '*'를 허용할 수 없습니다")
        if len(self.jwt_secret.get_secret_value()) < MIN_PRODUCT_JWT_SECRET_LENGTH:
            problems.append(f"jwt_secret은 {MIN_PRODUCT_JWT_SECRET_LENGTH}자 이상이어야 합니다")
        if decode_fernet_key(self.settings_encryption_key.get_secret_value()) == _EXAMPLE_KEY_BYTES:
            problems.append("settings_encryption_key에 예시 키를 쓸 수 없습니다")
        if self.sentry_dsn is None:
            problems.append("sentry_dsn이 필요합니다")
        if problems:
            raise ValueError("; ".join(problems))
        return self
