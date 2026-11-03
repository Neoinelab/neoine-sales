"""앱 자체 계정 관리 API의 OpenAPI 계약 (AC-1·6~11·15): 경로·메서드·응답 코드·스키마.

커밋된 openapi.json과의 일치(드리프트)는 functional/platform이 검사한다. 이 파일은 핵심을 직접
고정해 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _schema(spec: dict[str, Any], name: str) -> dict[str, Any]:
    schema: dict[str, Any] = spec["components"]["schemas"][name]
    return schema


def _request_schema_name(spec: dict[str, Any], method: str, path: str) -> str:
    ref = spec["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    return str(ref).rsplit("/", 1)[-1]


def _response_codes(spec: dict[str, Any], method: str, path: str) -> set[str]:
    return set(spec["paths"][path][method]["responses"])


def test_new_paths_and_methods(spec: dict[str, Any]) -> None:
    paths = spec["paths"]

    assert set(paths["/api/v1/auth/setup/auth-mode"]) == {"put"}
    assert set(paths["/api/v1/users/{user_id}"]) == {"delete", "patch"}
    assert set(paths["/api/v1/users/{user_id}/password"]) == {"put"}
    assert set(paths["/api/v1/me/profile"]) == {"get", "patch"}
    assert set(paths["/api/v1/me/password"]) == {"put"}


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("put", "/api/v1/auth/setup/auth-mode", {"204", "409", "422"}),
        ("patch", "/api/v1/users/{user_id}", {"200", "401", "403", "404", "409", "422"}),
        ("put", "/api/v1/users/{user_id}/password", {"204", "401", "403", "404", "409", "422"}),
        ("get", "/api/v1/me/profile", {"200", "401"}),
        ("patch", "/api/v1/me/profile", {"200", "401", "409", "422"}),
        ("put", "/api/v1/me/password", {"204", "401", "409", "422", "429"}),
        ("put", "/api/v1/settings/directory", {"409"}),
        ("post", "/api/v1/settings/directory/test", {"409"}),
    ],
)
def test_documented_success_and_problem_responses(
    spec: dict[str, Any], method: str, path: str, expected: set[str]
) -> None:
    assert expected <= _response_codes(spec, method, path)


def test_the_no_content_responses_have_no_body(spec: dict[str, Any]) -> None:
    for method, path in (
        ("put", "/api/v1/auth/setup/auth-mode"),
        ("put", "/api/v1/users/{user_id}/password"),
        ("put", "/api/v1/me/password"),
    ):
        assert "content" not in spec["paths"][path][method]["responses"]["204"]


def test_auth_config_has_exactly_the_setup_keys_without_dev_login(spec: dict[str, Any]) -> None:
    schema = _schema(spec, "AuthConfigResponse")

    assert set(schema["properties"]) == {
        "directory_login",
        "needs_directory_setup",
        "needs_storage_setup",
        "needs_admin_setup",
        "auth_mode",
    }
    assert "auth_mode" in schema["required"]
    options = schema["properties"]["auth_mode"]["anyOf"]
    assert {"type": "null"} in options


def test_the_dev_login_path_and_schema_are_gone(spec: dict[str, Any]) -> None:
    assert "/api/v1/auth/dev-login" not in spec["paths"]
    assert "DevLoginRequest" not in spec["components"]["schemas"]
    assert "dev_login" not in _schema(spec, "AuthConfigResponse")["properties"]


def test_auth_mode_request_takes_only_the_mode(spec: dict[str, Any]) -> None:
    name = _request_schema_name(spec, "put", "/api/v1/auth/setup/auth-mode")
    schema = _schema(spec, name)

    assert set(schema["properties"]) == {"mode"}
    assert schema["required"] == ["mode"]
    assert schema.get("additionalProperties") is False


def test_user_response_has_a_nullable_phone(spec: dict[str, Any]) -> None:
    schema = _schema(spec, "UserResponse")

    assert "phone" in schema["properties"]
    assert "phone" in schema["required"]
    assert {"type": "null"} in schema["properties"]["phone"]["anyOf"]


def test_user_request_has_optional_profile_fields_and_a_secret_password(
    spec: dict[str, Any],
) -> None:
    schema = _schema(spec, "UserRequest")

    assert {"login_id", "role", "display_name", "email", "phone", "password"} == set(
        schema["properties"]
    )
    assert set(schema["required"]) == {"login_id", "role"}
    password = next(
        option
        for option in schema["properties"]["password"]["anyOf"]
        if option.get("type") == "string"
    )
    assert (password.get("format"), password.get("writeOnly")) == ("password", True)


def test_the_profile_patch_requests_take_only_the_three_fields(spec: dict[str, Any]) -> None:
    for method, path in (("patch", "/api/v1/users/{user_id}"), ("patch", "/api/v1/me/profile")):
        schema = _schema(spec, _request_schema_name(spec, method, path))
        assert set(schema["properties"]) == {"display_name", "email", "phone"}
        assert not schema.get("required")
        assert schema.get("additionalProperties") is False


def test_password_requests_are_masked_write_only_secrets(spec: dict[str, Any]) -> None:
    cases = (
        ("put", "/api/v1/users/{user_id}/password", ("password",)),
        ("put", "/api/v1/me/password", ("current_password", "new_password")),
        ("post", "/api/v1/auth/setup", ("password",)),
        ("post", "/api/v1/auth/login", ("password",)),
    )
    for method, path, fields in cases:
        schema = _schema(spec, _request_schema_name(spec, method, path))
        assert set(fields) <= set(schema["properties"])
        for field in fields:
            prop = schema["properties"][field]
            assert (prop.get("format"), prop.get("writeOnly")) == ("password", True), (path, field)
            assert prop.get("maxLength") == 256


def test_setup_admin_request_has_the_optional_profile_fields(spec: dict[str, Any]) -> None:
    schema = _schema(spec, "SetupAdminRequest")

    assert {"login_id", "password", "display_name", "email", "phone"} == set(schema["properties"])
    assert set(schema["required"]) == {"login_id", "password"}


def test_my_profile_response_shape(spec: dict[str, Any]) -> None:
    name = spec["paths"]["/api/v1/me/profile"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].rsplit("/", 1)[-1]
    schema = _schema(spec, name)

    assert set(schema["properties"]) == {
        "id",
        "login_id",
        "role",
        "display_name",
        "email",
        "phone",
        "auth_mode",
        "editable",
    }
    assert schema["properties"]["id"]["type"] == "integer"
    editable_ref = schema["properties"]["editable"]["$ref"].rsplit("/", 1)[-1]
    editable = _schema(spec, editable_ref)
    assert set(editable["properties"]) == {"display_name", "email", "phone", "password"}
    assert all(p["type"] == "boolean" for p in editable["properties"].values())
    assert set(editable["required"]) == {"display_name", "email", "phone", "password"}


def test_both_profile_endpoints_return_the_same_response_schema(spec: dict[str, Any]) -> None:
    def name(method: str) -> str:
        ref = spec["paths"]["/api/v1/me/profile"][method]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        return str(ref)

    assert name("get") == name("patch")
