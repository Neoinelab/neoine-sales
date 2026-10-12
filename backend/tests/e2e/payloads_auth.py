"""인증·최초 설정 e2e의 요청 본문과 공통 상수."""

from typing import Any

from tests.factories_auth import ADMIN_PASSWORD, BASE_DN, BIND_TEMPLATE, USER_FILTER

LOGIN = "/api/v1/auth/login"
SETUP = "/api/v1/auth/setup"
SETUP_DIRECTORY = "/api/v1/auth/setup/directory"
CONFIG = "/api/v1/auth/config"
ME = "/api/v1/auth/me"
USERS = "/api/v1/users"
SETTINGS = "/api/v1/settings/directory"
SETTINGS_TEST = "/api/v1/settings/directory/test"
PROBLEM_PREFIX = "https://neoine-sales.example/problems/"


def directory_payload(**overrides: object) -> dict[str, Any]:
    """PUT /auth/setup/directory 본문(DirectorySettingsRequest). 유효한 더미 값."""
    values: dict[str, Any] = {
        "server_urls": ["ldaps://dc1.corp.test"],
        "use_starttls": False,
        "ca_cert_pem": None,
        "bind_template": BIND_TEMPLATE,
        "base_dn": BASE_DN,
        "user_filter": USER_FILTER,
        "display_name_attribute": "displayName",
        "email_attribute": "mail",
        "connect_timeout_seconds": 5,
        "receive_timeout_seconds": 10,
    }
    return {**values, **overrides}


def credentials(login_id: str = "kim", password: str = "pw-kim") -> dict[str, str]:  # noqa: S107
    return {"login_id": login_id, "password": password}


def problem_type(body: dict[str, Any]) -> str:
    return str(body["type"]).removeprefix(PROBLEM_PREFIX)


def settings_update_payload(
    expected_revision: int = 1,
    password: str | None = ADMIN_PASSWORD,
    **overrides: object,
) -> dict[str, Any]:
    """PUT /settings/directory 본문: 설정 필드 + expected_revision + 현재 admin의 password."""
    return {
        **directory_payload(**overrides),
        "expected_revision": expected_revision,
        "password": password,
    }


def settings_test_payload(
    password: str | None = ADMIN_PASSWORD, **overrides: object
) -> dict[str, Any]:
    """POST /settings/directory/test 본문: 설정 필드 + 현재 admin의 password."""
    return {**directory_payload(**overrides), "password": password}
