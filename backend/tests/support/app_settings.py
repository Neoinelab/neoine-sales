"""단위 테스트가 쓰는 앱 설정·HTTP 공통 값."""

from typing import Final

from app.config.profiles import LocalSettings
from tests.support.crypto_keys import TEST_FERNET_KEY

ALLOWED_ORIGIN: Final = "http://localhost:5173"
CSRF_HEADER: Final = {"X-Requested-With": "neoine-web"}
# 사용자 응답(UserResponse)이 가져야 하는 키 전체
USER_KEYS: Final = {
    "id",
    "login_id",
    "role",
    "display_name",
    "email",
    "phone",
    "created_at",
    "created_by",
    "last_login_at",
    "status",
    "deleted_at",
    "delete_reason",
}


def make_settings(database_url: str, **overrides: object) -> LocalSettings:
    """실제 환경 파일을 읽지 않는 테스트용 local 설정(비밀은 더미 값)."""
    values: dict[str, object] = {
        "database_url": database_url,
        "jwt_secret": "x" * 40,
        "settings_encryption_key": TEST_FERNET_KEY,
        "cors_allowed_origins": [ALLOWED_ORIGIN],
    }
    return LocalSettings(_env_file=None, **{**values, **overrides})  # type: ignore[arg-type]
