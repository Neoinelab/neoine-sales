"""OpenAPI 계약 시나리오의 Then step: 반복해서 확인해야 하는 항목을 한 이름으로 묶는다.

모든 step은 `/openapi.json` 조회 응답을 받아 그 계약을 확인한다.
"""

from typing import TYPE_CHECKING, Any

from tests.functional.steps.platform import (
    operation_of,
    property_names_of,
    response_schema_names,
    schema_name_of,
    spec_of,
)

if TYPE_CHECKING:
    from httpx import Response

AUTH_PASSWORD_REQUESTS = ("LoginRequest", "SetupAdminRequest")
SETTINGS_PASSWORD_REQUESTS = (
    ("PUT", "/api/v1/settings/directory"),
    ("POST", "/api/v1/settings/directory/test"),
)
USER_REF_FIELDS = (
    ("DealDetailResponse", "owner"),
    ("DealRowResponse", "owner"),
    ("DealActionResponse", "actor"),
    ("HistoryEntryResponse", "by"),
    ("BantLabelResponse", "created_by"),
    ("UserResponse", "created_by"),
    ("DirectorySettingsResponse", "updated_by"),
    ("StorageSettingsResponse", "updated_by"),
    ("AttachmentResponse", "uploaded_by"),
)


# ------------------------------------------------------------------ 인증 API


def then_no_response_schema_has_a_password_field(response: Response) -> None:
    """어떤 응답 스키마(중첩 포함)에도 비밀번호 필드가 없다."""
    spec = spec_of(response)
    for name in response_schema_names(spec):
        leaked = {p for p in property_names_of(spec, name) if "password" in p.lower()}
        assert not leaked, f"{name} 응답에 비밀번호 필드가 있다: {leaked}"


def then_login_and_setup_passwords_are_masked_secrets(response: Response) -> None:
    """로그인·최초 설정 요청의 password는 마스킹되는 쓰기 전용 비밀 값이다."""
    schemas = spec_of(response)["components"]["schemas"]
    for name in AUTH_PASSWORD_REQUESTS:
        password = schemas[name]["properties"]["password"]
        assert password.get("format") == "password"
        assert password.get("writeOnly") is True


# ------------------------------------------------------------------ 계약 파일 일치


def then_every_endpoint_documents_its_error_responses(response: Response) -> None:
    """인증 API를 뺀 모든 엔드포인트가 401(그리고 입력이 있으면 422) 응답을 문서화한다."""
    for path, operations in spec_of(response)["paths"].items():
        if not path.startswith("/api/v1/") or path.startswith("/api/v1/auth/"):
            continue
        for method, operation in operations.items():
            responses = operation["responses"]
            has_input = "parameters" in operation or "requestBody" in operation
            if has_input:  # 입력이 없는 엔드포인트(GET /settings/directory)는 422가 나올 수 없다
                assert "422" in responses, f"{method.upper()} {path}에 422 응답 문서가 없다"
            assert "401" in responses, f"{method.upper()} {path}에 401 응답 문서가 없다"


def _max_lengths(parameter: dict[str, Any]) -> list[int]:
    return [option["maxLength"] for option in parameter["schema"]["anyOf"] if "maxLength" in option]


def then_deal_search_text_params_document_max_length(response: Response) -> None:
    """Deal 검색의 keyword는 최대 길이 100을, Vendor·Solution 조건은 정수 id를 문서화한다."""
    params = {
        p["name"]: p for p in spec_of(response)["paths"]["/api/v1/deals"]["get"]["parameters"]
    }
    assert _max_lengths(params["keyword"]) == [100], "keyword 파라미터에 maxLength 100이 없다"
    assert not {"vendor", "solution"} & set(params)  # 이름 조건은 id 조건으로 바뀌었다
    for name in ("vendor_id", "solution_id"):
        kinds = {o.get("type") for o in params[name]["schema"]["anyOf"]}
        assert "integer" in kinds, f"{name} 파라미터가 정수가 아니다"
    assert "owner" not in params  # 텍스트 담당자 필터는 owner_user_id(정수)로 바뀌었다
    owner_types = {o.get("type") for o in params["owner_user_id"]["schema"]["anyOf"]}
    assert "integer" in owner_types


def then_contact_search_params_document_max_length(response: Response) -> None:
    """연락처 검색 파라미터(kind, keyword, offset, limit)와 keyword 최대 길이(100)가 문서화된다."""
    schema = spec_of(response)
    params = {p["name"]: p for p in schema["paths"]["/api/v1/contacts"]["get"]["parameters"]}
    assert {"kind", "keyword", "offset", "limit"} <= set(params)
    assert _max_lengths(params["keyword"]) == [100], "keyword에 maxLength 100이 없다"


def then_contact_delete_documents_the_409(response: Response) -> None:
    """연락처 삭제는 참조하는 Deal이 있을 때의 409 응답을 문서화한다."""
    schema = spec_of(response)
    responses = schema["paths"]["/api/v1/contacts/{contact_id}"]["delete"]["responses"]
    assert "409" in responses, "DELETE /contacts/{contact_id}에 409 응답 문서가 없다"


def then_retired_customer_and_partner_paths_are_not_documented(response: Response) -> None:
    """폐지된 고객·파트너 경로는 OpenAPI에 없고 contacts 경로가 있다."""
    paths = set(spec_of(response)["paths"])
    assert not [p for p in paths if p.startswith(("/api/v1/customers", "/api/v1/partners"))]
    assert {
        "/api/v1/contacts",
        "/api/v1/contacts/companies",
        "/api/v1/contacts/by-company",
    } <= paths
    assert "/api/v1/contacts/{contact_id}" in paths


# ------------------------------------------------------------------ 역할·사용자 API


def then_every_user_display_uses_user_ref(response: Response) -> None:
    """응답에서 사용자를 보여 주는 모든 필드는 UserRef 스키마를 쓴다."""
    schemas = spec_of(response)["components"]["schemas"]
    for schema, field in USER_REF_FIELDS:
        assert "UserRef" in str(schemas[schema]["properties"][field]), (schema, field)


def then_user_delete_documents_outcome_reason_and_errors(response: Response) -> None:
    """사용자 삭제는 200 결과(deleted·resigned), reason 쿼리, 오류 응답을 문서화한다."""
    spec = spec_of(response)
    operation = operation_of(spec, "DELETE", "/api/v1/users/{user_id}")
    assert "204" not in operation["responses"]
    assert "200" in operation["responses"]
    for code in ("401", "403", "404", "409", "422"):
        assert code in operation["responses"], code
    body = spec["components"]["schemas"][schema_name_of(operation, request=False)]
    assert set(body["properties"]) == {"outcome"}
    assert set(body["properties"]["outcome"]["enum"]) == {"deleted", "resigned"}
    reason = next(p for p in operation["parameters"] if p["name"] == "reason")
    assert reason["in"] == "query"
    assert reason["schema"]["enum"] == ["resigned"]
    assert reason["schema"]["default"] == "resigned"


def then_user_options_document_filters_and_only_the_ref_fields(response: Response) -> None:
    """사용자 선택 목록은 필터를 문서화하고 UserRef 항목만 공개한다."""
    spec = spec_of(response)
    operation = operation_of(spec, "GET", "/api/v1/user-options")
    params = {p["name"]: p for p in operation["parameters"]}
    assert {"include_resigned", "keyword", "role"} <= set(params)
    assert "limit" not in params  # 페이징 없이 전부 돌려준다
    assert params["include_resigned"]["schema"]["default"] is False
    page = spec["components"]["schemas"][schema_name_of(operation, request=False)]
    assert "items" in page["properties"]
    assert "UserRef" in str(page["properties"]["items"])
    for code in ("401", "422"):
        assert code in operation["responses"], code


def _password_property(schema: dict[str, Any]) -> dict[str, Any]:
    prop: dict[str, Any] = schema["properties"]["password"]
    options = [o for o in prop.get("anyOf", []) if o.get("type") == "string"]
    return options[0] if options else prop


def then_settings_request_passwords_are_masked_write_only_secrets(response: Response) -> None:
    """AD 설정 저장·연결 테스트 요청의 password는 마스킹되는 쓰기 전용 비밀 값이다."""
    spec = spec_of(response)
    for method, path in SETTINGS_PASSWORD_REQUESTS:
        name = schema_name_of(operation_of(spec, method, path), request=True)
        password = _password_property(spec["components"]["schemas"][name])
        assert password.get("format") == "password", name
        assert password.get("writeOnly") is True, name
