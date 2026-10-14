"""역할·관리 API의 OpenAPI 계약 (ROLE-6, USER-1·8, AUTH-7, T-E35)."""

from typing import Any

import pytest

from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.e2e.permission_table import ADMIN_ONLY, BUSINESS_READS, BUSINESS_WRITES, LOGGED_IN_ANY
from tests.fakes.use_cases import FakeUseCases

PROTECTED = [*BUSINESS_READS, *BUSINESS_WRITES, *ADMIN_ONLY, *LOGGED_IN_ANY]
FORBIDDEN_DOCUMENTED = [*BUSINESS_WRITES, *ADMIN_ONLY]


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()


def _operation(spec: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    operation: dict[str, Any] = spec["paths"][path][method.lower()]
    return operation


def _schema_name(operation: dict[str, Any], *, request: bool) -> str:
    if request:
        ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    else:
        ref = next(
            r["content"]["application/json"]["schema"]["$ref"]
            for code, r in operation["responses"].items()
            if code.startswith("2") and "content" in r
        )
    return str(ref).rsplit("/", 1)[-1]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_protected_endpoints_document_401(spec: dict[str, Any], method: str, path: str) -> None:
    assert "401" in _operation(spec, method, path)["responses"]


@pytest.mark.parametrize(("method", "path"), FORBIDDEN_DOCUMENTED)
def test_write_and_admin_endpoints_document_403_with_the_problem_schema(
    spec: dict[str, Any], method: str, path: str
) -> None:
    response = _operation(spec, method, path)["responses"]["403"]

    ref = response["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/Problem")


@pytest.mark.parametrize(("method", "path"), BUSINESS_READS)
def test_read_endpoints_do_not_document_403(spec: dict[str, Any], method: str, path: str) -> None:
    assert "403" not in _operation(spec, method, path)["responses"]


def test_user_management_paths_have_exactly_the_planned_methods(spec: dict[str, Any]) -> None:
    paths = spec["paths"]

    assert set(paths["/api/v1/users"]) == {"get", "post"}
    assert set(paths["/api/v1/users/{user_id}"]) == {"delete"}
    assert set(paths["/api/v1/settings/directory"]) == {"get", "put"}
    assert set(paths["/api/v1/settings/directory/test"]) == {"post"}


def test_user_response_has_the_documented_fields_and_no_password(spec: dict[str, Any]) -> None:
    name = _schema_name(_operation(spec, "POST", "/api/v1/users"), request=False)

    assert set(spec["components"]["schemas"][name]["properties"]) == {
        "id",
        "login_id",
        "role",
        "display_name",
        "email",
        "created_at",
        "created_by",
        "last_login_at",
        "status",
        "deleted_at",
        "delete_reason",
    }


def test_user_ref_schema_has_the_four_documented_fields_and_no_login_id(
    spec: dict[str, Any],
) -> None:
    properties = spec["components"]["schemas"]["UserRef"]["properties"]

    assert set(properties) == {"id", "name", "resigned", "label"}
    assert properties["resigned"]["type"] == "boolean"


def test_every_user_display_in_responses_uses_user_ref(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]

    for schema, field in (
        ("DealResponse", "owner"),
        ("DealActionResponse", "actor"),
        ("DealStageChangeResponse", "changed_by"),
        ("UserResponse", "created_by"),
    ):
        assert "UserRef" in str(schemas[schema]["properties"][field]), (schema, field)
    updated_by = next(s for name, s in schemas.items() if "updated_by" in s.get("properties", {}))
    assert "UserRef" in str(updated_by["properties"]["updated_by"])


def test_users_list_documents_the_status_filter_with_active_as_default(
    spec: dict[str, Any],
) -> None:
    params = {p["name"]: p for p in _operation(spec, "GET", "/api/v1/users")["parameters"]}

    status = params["status"]["schema"]
    assert set(status["enum"]) == {"active", "resigned", "all"}
    assert status["default"] == "active"
    assert not params["status"].get("required")


def test_user_delete_documents_200_outcome_reason_query_and_the_error_responses(
    spec: dict[str, Any],
) -> None:
    operation = _operation(spec, "DELETE", "/api/v1/users/{user_id}")

    assert "204" not in operation["responses"]
    assert "200" in operation["responses"]
    for code in ("401", "403", "404", "409", "422"):
        assert code in operation["responses"], code
    body = spec["components"]["schemas"][_schema_name(operation, request=False)]
    assert set(body["properties"]) == {"outcome"}
    assert set(body["properties"]["outcome"]["enum"]) == {"deleted", "resigned"}
    reason = next(p for p in operation["parameters"] if p["name"] == "reason")
    assert reason["in"] == "query"
    assert reason["schema"]["enum"] == ["resigned"]
    assert reason["schema"]["default"] == "resigned"


def test_user_options_endpoint_documents_filters_and_exposes_only_the_ref_fields(
    spec: dict[str, Any],
) -> None:
    operation = _operation(spec, "GET", "/api/v1/user-options")

    params = {p["name"]: p for p in operation["parameters"]}
    assert {"include_resigned", "keyword", "limit"} <= set(params)
    assert params["include_resigned"]["schema"]["default"] is False
    page = spec["components"]["schemas"][_schema_name(operation, request=False)]
    assert "items" in page["properties"]
    assert "UserRef" in str(page["properties"]["items"])
    for code in ("401", "422"):
        assert code in operation["responses"], code


def test_auth_me_response_documents_the_user_id(spec: dict[str, Any]) -> None:
    name = _schema_name(_operation(spec, "GET", "/api/v1/auth/me"), request=False)

    assert "user_id" in spec["components"]["schemas"][name]["properties"]


def test_user_register_request_takes_only_login_id_and_role(spec: dict[str, Any]) -> None:
    name = _schema_name(_operation(spec, "POST", "/api/v1/users"), request=True)

    assert set(spec["components"]["schemas"][name]["properties"]) == {"login_id", "role"}


def test_user_list_is_a_page_of_user_responses(spec: dict[str, Any]) -> None:
    page = spec["components"]["schemas"][
        _schema_name(_operation(spec, "GET", "/api/v1/users"), request=False)
    ]

    assert set(page["properties"]) == {"items", "offset", "limit"}


def test_settings_request_passwords_are_masked_write_only_secrets(spec: dict[str, Any]) -> None:
    for method, path in (
        ("PUT", "/api/v1/settings/directory"),
        ("POST", "/api/v1/settings/directory/test"),
    ):
        name = _schema_name(_operation(spec, method, path), request=True)
        password = _password_property(spec["components"]["schemas"][name])
        assert password.get("format") == "password", name
        assert password.get("writeOnly") is True, name


def _password_property(schema: dict[str, Any]) -> dict[str, Any]:
    prop: dict[str, Any] = schema["properties"]["password"]
    options = [o for o in prop.get("anyOf", []) if o.get("type") == "string"]
    return options[0] if options else prop


def test_settings_update_request_requires_the_expected_revision(spec: dict[str, Any]) -> None:
    name = _schema_name(_operation(spec, "PUT", "/api/v1/settings/directory"), request=True)
    schema = spec["components"]["schemas"][name]

    assert "expected_revision" in schema["required"]
    assert (
        "expected_revision"
        not in spec["components"]["schemas"][
            _schema_name(_operation(spec, "POST", "/api/v1/settings/directory/test"), request=True)
        ]["properties"]
    )


def test_settings_test_result_has_success_stage_and_message(spec: dict[str, Any]) -> None:
    name = _schema_name(_operation(spec, "POST", "/api/v1/settings/directory/test"), request=False)

    assert set(spec["components"]["schemas"][name]["properties"]) == {"success", "stage", "message"}
