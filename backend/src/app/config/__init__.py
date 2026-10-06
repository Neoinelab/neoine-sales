"""애플리케이션 설정 진입점.

APP_PROFILE(local|dev|product)에 따라 설정 클래스를 선택한다(환경변수 또는 .env). 미설정 시 local.
domain/application 계층은 이 패키지를 import하지 않는다. 읽는 곳은 container.py와 앱 팩토리뿐이다.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.base import Profile, Settings
from app.config.profiles import DevSettings, LocalSettings, ProductSettings

_BY_PROFILE: dict[Profile, type[Settings]] = {
    Profile.LOCAL: LocalSettings,
    Profile.DEV: DevSettings,
    Profile.PRODUCT: ProductSettings,
}


class _ProfileSelector(BaseSettings):
    """APP_PROFILE만 먼저 읽는다. 환경변수 또는 .env 파일 어디에 있어도 된다."""

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    profile: Profile = Profile.LOCAL


@lru_cache
def get_settings() -> Settings:
    profile = _ProfileSelector().profile  # 잘못된 값이면 즉시 실패
    return _BY_PROFILE[profile]()


__all__ = ["Profile", "Settings", "get_settings"]
