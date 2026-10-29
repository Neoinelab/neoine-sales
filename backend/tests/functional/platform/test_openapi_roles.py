"""Feature: 역할·사용자 관리 API는 권한 응답과 필드 구성을 OpenAPI 계약으로 정확히 공개한다."""

from typing import TYPE_CHECKING, Any

import pytest

from tests.functional.steps.openapi_checks import (
    then_every_user_display_uses_user_ref,
    then_settings_request_passwords_are_masked_write_only_secrets,
    then_user_delete_documents_outcome_reason_and_errors,
    then_user_options_document_filters_and_only_the_ref_fields,
)
from tests.functional.steps.permissions import (
    ADMIN_ONLY,
    BUSINESS_READS,
    BUSINESS_WRITES,
    LOGGED_IN_ANY,
    route_id,
)
from tests.functional.steps.platform import (
    operation_of,
    schema_name_of,
    spec_of,
    when_fetch_openapi,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
PROTECTED = [*BUSINESS_READS, *BUSINESS_WRITES, *ADMIN_ONLY, *LOGGED_IN_ANY]
FORBIDDEN_DOCUMENTED = [*BUSINESS_WRITES, *ADMIN_ONLY]


def _ids(routes: list[tuple[str, str]] | tuple[tuple[str, str], ...]) -> list[str]:
    return [route_id(route) for route in routes]


@pytest.mark.parametrize(("method", "path"), PROTECTED, ids=_ids(PROTECTED))
async def test_protected_endpoints_document_401(api: Api, method: str, path: str) -> None:
    """Scenario: 로그인이 필요한 모든 엔드포인트는 401 응답을 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    assert "401" in operation_of(spec_of(response), method, path)["responses"]


@pytest.mark.parametrize(("method", "path"), FORBIDDEN_DOCUMENTED, ids=_ids(FORBIDDEN_DOCUMENTED))
async def test_write_and_admin_endpoints_document_403_with_the_problem_schema(
    api: Api, method: str, path: str
) -> None:
    """Scenario: 쓰기·관리자 엔드포인트는 403 응답을 Problem 스키마로 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    documented = operation_of(spec_of(response), method, path)["responses"]["403"]
    ref = documented["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/Problem")


@pytest.mark.parametrize(("method", "path"), BUSINESS_READS, ids=_ids(BUSINESS_READS))
async def test_read_endpoints_do_not_document_403(api: Api, method: str, path: str) -> None:
    """Scenario: 모든 역할이 읽을 수 있는 조회 엔드포인트는 403을 문서화하지 않는다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    assert "403" not in operation_of(spec_of(response), method, path)["responses"]


async def test_user_management_paths_have_exactly_the_planned_methods(api: Api) -> None:
    """Scenario: 사용자 관리·AD 설정 경로는 계획된 HTTP 메서드만 공개한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    paths = spec_of(response)["paths"]
    assert set(paths["/api/v1/users"]) == {"get", "post"}
    assert set(paths["/api/v1/users/{user_id}"]) == {"delete"}
    assert set(paths["/api/v1/settings/directory"]) == {"get", "put"}
    assert set(paths["/api/v1/settings/directory/test"]) == {"post"}


async def test_user_response_has_the_documented_fields_and_no_password(api: Api) -> None:
    """Scenario: 사용자 응답은 문서화된 필드만 갖고 비밀번호 필드는 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    name = schema_name_of(operation_of(spec, "POST", "/api/v1/users"), request=False)
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


async def test_user_ref_schema_has_the_five_documented_fields_and_no_login_id(api: Api) -> None:
    """Scenario: UserRef는 id·name·resigned·label·role 다섯 필드뿐이며 login_id는 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    properties = spec_of(response)["components"]["schemas"]["UserRef"]["properties"]
    assert set(properties) == {"id", "name", "resigned", "label", "role"}
    assert properties["resigned"]["type"] == "boolean"
    assert properties["role"] == {"$ref": "#/components/schemas/Role"}


async def test_every_user_display_in_responses_uses_user_ref(api: Api) -> None:
    """Scenario: 응답에서 사용자를 보여 주는 모든 필드는 UserRef 스키마를 쓴다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_every_user_display_uses_user_ref(response)


async def test_users_list_documents_the_status_filter_with_active_as_default(api: Api) -> None:
    """Scenario: 사용자 목록은 상태 필터(active·resigned·all)를 문서화하고 기본값은 active다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    operation = operation_of(spec_of(response), "GET", "/api/v1/users")
    params = {p["name"]: p for p in operation["parameters"]}
    status = params["status"]["schema"]
    assert set(status["enum"]) == {"active", "resigned", "all"}
    assert status["default"] == "active"
    assert not params["status"].get("required")


async def test_user_delete_documents_200_outcome_reason_query_and_the_error_responses(
    api: Api,
) -> None:
    """Scenario: 사용자 삭제는 200 결과(deleted·resigned), reason 쿼리, 오류 응답을 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_user_delete_documents_outcome_reason_and_errors(response)


async def test_user_options_endpoint_documents_filters_and_exposes_only_the_ref_fields(
    api: Api,
) -> None:
    """Scenario: 사용자 선택 목록은 필터를 문서화하고 UserRef 항목만 공개한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_user_options_document_filters_and_only_the_ref_fields(response)


async def test_auth_me_response_documents_the_user_id(api: Api) -> None:
    """Scenario: 내 정보 응답은 user_id 필드를 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    name = schema_name_of(operation_of(spec, "GET", "/api/v1/auth/me"), request=False)
    assert "user_id" in spec["components"]["schemas"][name]["properties"]


async def test_user_register_request_takes_login_id_role_and_optional_display_name(
    api: Api,
) -> None:
    """Scenario: 사용자 등록 요청은 login_id·role과 선택값 display_name만 받는다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    name = schema_name_of(operation_of(spec, "POST", "/api/v1/users"), request=True)
    schema = spec["components"]["schemas"][name]
    assert set(schema["properties"]) == {"login_id", "role", "display_name"}
    assert set(schema["required"]) == {"login_id", "role"}


async def test_user_list_is_a_page_of_user_responses(api: Api) -> None:
    """Scenario: 사용자 목록 응답은 items·offset·limit을 가진 페이지다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    name = schema_name_of(operation_of(spec, "GET", "/api/v1/users"), request=False)
    assert set(spec["components"]["schemas"][name]["properties"]) == {"items", "offset", "limit"}


async def test_settings_request_passwords_are_masked_write_only_secrets(api: Api) -> None:
    """Scenario: AD 설정 저장·연결 테스트 요청의 password는 마스킹되는 쓰기 전용 비밀 값이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_settings_request_passwords_are_masked_write_only_secrets(response)


async def test_settings_update_request_requires_the_expected_revision(api: Api) -> None:
    """Scenario: 설정 저장 요청은 expected_revision이 필수이고 연결 테스트 요청에는 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    update = schema_name_of(operation_of(spec, "PUT", "/api/v1/settings/directory"), request=True)
    probe = schema_name_of(
        operation_of(spec, "POST", "/api/v1/settings/directory/test"), request=True
    )
    schemas = spec["components"]["schemas"]
    assert "expected_revision" in schemas[update]["required"]
    assert "expected_revision" not in schemas[probe]["properties"]


async def test_settings_test_result_has_success_stage_message_and_base_dn(api: Api) -> None:
    """Scenario: 연결 테스트 결과는 success·stage·message·base_dn 필드를 가진다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    operation = operation_of(spec, "POST", "/api/v1/settings/directory/test")
    name = schema_name_of(operation, request=False)
    assert set(spec["components"]["schemas"][name]["properties"]) == {
        "success",
        "stage",
        "message",
        "base_dn",
    }


CONNECTION_FIELDS = {
    "host",
    "port",
    "security",
    "bind_account",
    "bind_password",
    "user_filter",
    "connect_timeout_seconds",
}


async def test_directory_requests_accept_exactly_the_seven_connection_fields(api: Api) -> None:
    """Scenario: 최초 설정·설정 저장·연결 테스트 요청은 AD 입력 7개만 받는다(구 필드 없음)."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    schemas = spec["components"]["schemas"]
    setup = schemas[
        schema_name_of(operation_of(spec, "PUT", "/api/v1/auth/setup/directory"), request=True)
    ]
    update = schemas[
        schema_name_of(operation_of(spec, "PUT", "/api/v1/settings/directory"), request=True)
    ]
    probe = schemas[
        schema_name_of(operation_of(spec, "POST", "/api/v1/settings/directory/test"), request=True)
    ]
    assert set(setup["properties"]) == CONNECTION_FIELDS
    assert set(update["properties"]) == CONNECTION_FIELDS | {"password", "expected_revision"}
    assert set(probe["properties"]) == CONNECTION_FIELDS | {"password"}
    assert "bind_password" in setup["required"]  # 최초 설정은 비밀번호가 필수
    assert "bind_password" not in update["required"]  # 설정 화면은 생략하면 저장된 값 유지
    assert "bind_password" not in probe["required"]
    assert {"expected_revision"} <= set(update["required"])  # 키는 필수, 값은 null 가능


async def test_directory_settings_response_hides_the_password_and_shows_the_base_dn(
    api: Api,
) -> None:
    """Scenario: 설정 응답에는 바인드 비밀번호가 없고 저장 상태와 읽기 전용 Base DN이 있다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    name = schema_name_of(operation_of(spec, "GET", "/api/v1/settings/directory"), request=False)
    properties = spec["components"]["schemas"][name]["properties"]
    assert {"bind_credential_status", "base_dn", "bind_account", "host", "port", "security"} <= set(
        properties
    )
    assert not any("password" in key for key in properties)
    assert set(properties["bind_credential_status"].get("enum", [])) == {"ok", "unreadable"}


async def test_login_response_has_the_directory_warning(api: Api) -> None:
    """Scenario: 로그인 응답은 기존 필드에 더해 directory_warning(또는 null)을 가진다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    name = schema_name_of(operation_of(spec, "POST", "/api/v1/auth/login"), request=False)
    properties = spec["components"]["schemas"][name]["properties"]
    assert "directory_warning" in properties
    assert {"user_id", "subject", "role"} <= set(properties)


def _is_masked_secret(prop: dict[str, Any]) -> bool:
    candidates = [prop, *prop.get("anyOf", [])]
    return any(c.get("format") == "password" and c.get("writeOnly") is True for c in candidates)


async def test_bind_password_is_a_masked_write_only_secret_in_every_directory_request(
    api: Api,
) -> None:
    """Scenario: 바인드 비밀번호는 세 AD 요청 모두에서 마스킹되는 쓰기 전용 비밀 값이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    for method, path in (
        ("PUT", "/api/v1/auth/setup/directory"),
        ("PUT", "/api/v1/settings/directory"),
        ("POST", "/api/v1/settings/directory/test"),
    ):
        name = schema_name_of(operation_of(spec, method, path), request=True)
        prop = spec["components"]["schemas"][name]["properties"]["bind_password"]
        assert _is_masked_secret(prop), (path, prop)
