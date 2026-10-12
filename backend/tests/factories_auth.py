"""인증·사용자·AD 설정 테스트용 생성 도우미. 기본은 유효한 더미 값이고 overrides로 일부만 바꾼다."""

from datetime import timedelta
from typing import Any

from app.domain.auth.credentials import LoginId
from app.domain.auth.login_failure import FailureCounter, FailurePolicy
from app.domain.auth.principal import Role
from app.domain.directory.settings import DirectorySettings, DirectoryUrl
from app.domain.user.entities import User
from tests.factories import NOW

BIND_TEMPLATE = "cn={login_id},ou=users,dc=corp,dc=test"
BASE_DN = "dc=corp,dc=test"
USER_FILTER = "(&(objectClass=user)(sAMAccountName={login_id}))"
ADMIN_LOGIN = "root"  # 관리 API 테스트의 admin 아이디(AD 계정도 같은 이름)
ADMIN_PASSWORD = "pw-root"  # noqa: S105 - 가짜 값
WRONG_PASSWORD = "wrong-password"  # noqa: S105 - 가짜 값
CERT_BEGIN = "-----BEGIN CERTIFICATE-----"
CERT_END = "-----END CERTIFICATE-----"
# 도메인은 형식(CERTIFICATE 블록)만 본다. 실제 인증서가 아니라 base64 문자만 채운 더미다.
DUMMY_PEM = f"{CERT_BEGIN}\n{'A' * 64}\n{'B' * 40}\n{CERT_END}\n"


def make_directory_settings(**overrides: object) -> DirectorySettings:
    values: dict[str, Any] = {
        "server_urls": (DirectoryUrl.parse("ldaps://dc1.corp.test"),),
        "use_starttls": False,
        "ca_cert_pem": None,
        "bind_template": BIND_TEMPLATE,
        "base_dn": BASE_DN,
        "user_filter": USER_FILTER,
    }
    return DirectorySettings(**{**values, **overrides})


def make_user(login_id: str = "kim", role: Role = Role.SALES, **overrides: object) -> User:
    values: dict[str, Any] = {"created_by": "admin", "now": NOW}
    return User.register(LoginId(login_id), role, **{**values, **overrides})


def make_policy(**overrides: object) -> FailurePolicy:
    values: dict[str, Any] = {
        "max_failures": 5,
        "window": timedelta(minutes=15),
        "lock_duration": timedelta(minutes=15),
    }
    return FailurePolicy(**{**values, **overrides})


def make_counter(key: str = "k" * 64, **overrides: object) -> FailureCounter:
    values: dict[str, Any] = {"failures": 0, "window_started_at": NOW, "locked_until": None}
    return FailureCounter(key=key, **{**values, **overrides})
