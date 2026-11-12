"""앱이 공개하는 OpenAPI 계약의 개별 문서화 항목(Deal·연락처·사용자 관리).

옛 functional/platform의 OpenAPI 시나리오를 단위 테스트로 옮긴 것이다. 계약은 Fake 유스케이스로
조립한 앱의 `openapi()`이고(DB 접속 없음), 커밋 파일과의 일치는 PL-034가 본다.
"""

from typing import Any

import pytest

from tests.support.openapi_spec import app_contract, operation_of

Spec = dict[str, Any]
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


@pytest.fixture(scope="module")
def spec() -> Spec:
    return app_contract()


def _max_lengths(parameter: dict[str, Any]) -> list[int]:
    return [option["maxLength"] for option in parameter["schema"]["anyOf"] if "maxLength" in option]


def _params(spec: Spec, path: str) -> dict[str, dict[str, Any]]:
    return {p["name"]: p for p in operation_of(spec, "GET", path)["parameters"]}


def _response_schema(spec: Spec, operation: dict[str, Any]) -> dict[str, Any]:
    ref = next(
        r["content"]["application/json"]["schema"]["$ref"]
        for code, r in operation["responses"].items()
        if code.startswith("2") and "content" in r
    )
    schema: dict[str, Any] = spec["components"]["schemas"][str(ref).rsplit("/", 1)[-1]]
    return schema


def test_deal_search_text_params_document_their_max_length_and_id_types(spec: Spec) -> None:
    """Deal 검색의 keyword·solution은 길이 상한이 있고 vendor_id·owner_user_id는 정수다."""
    # when: Deal 목록 파라미터를 읽는다
    params = _params(spec, "/api/v1/deals")
    # then: 길이 상한이 있고 폐지된 텍스트 조건은 없다
    assert _max_lengths(params["keyword"]) == [100]
    assert _max_lengths(params["solution"]) == [200]
    assert {"vendor", "solution_id", "owner"}.isdisjoint(params)
    for name in ("vendor_id", "owner_user_id"):
        assert "integer" in {o.get("type") for o in params[name]["schema"]["anyOf"]}


def test_contact_search_params_document_the_keyword_max_length(spec: Spec) -> None:
    """연락처 검색은 kind·keyword·offset·limit을 받고 keyword는 최대 100자로 문서화된다."""
    # when: 연락처 목록 파라미터를 읽는다
    params = _params(spec, "/api/v1/contacts")
    # then: kind·keyword·offset·limit가 있고 keyword는 최대 100자다
    assert {"kind", "keyword", "offset", "limit"} <= set(params)
    assert _max_lengths(params["keyword"]) == [100]


def test_retired_customer_and_partner_paths_are_gone_and_contact_paths_exist(spec: Spec) -> None:
    """폐지된 고객·파트너 경로는 문서에 없고 contacts 경로 네 개가 있다."""
    # when: 문서화된 경로를 본다
    paths = set(spec["paths"])
    # then: 고객·파트너 경로는 없고 contacts 경로 네 개가 있다
    assert not [p for p in paths if p.startswith(("/api/v1/customers", "/api/v1/partners"))]
    assert {
        "/api/v1/contacts",
        "/api/v1/contacts/companies",
        "/api/v1/contacts/by-company",
        "/api/v1/contacts/{contact_id}",
    } <= paths


def test_contact_delete_documents_the_409_for_referencing_deals(spec: Spec) -> None:
    """연락처 삭제는 참조하는 Deal이 있을 때의 409 응답을 문서화한다."""
    # when: 연락처 삭제의 응답 목록을 읽는다
    responses = operation_of(spec, "DELETE", "/api/v1/contacts/{contact_id}")["responses"]
    # then: 409 응답이 있다
    assert "409" in responses


def test_deal_endpoints_use_the_code_path_and_the_deals_tag(spec: Spec) -> None:
    """Deal 엔드포인트는 code 경로이고 deals 태그로 묶이며 폐지 경로는 없다."""
    # when: Deal 경로의 메서드와 태그를 읽는다
    paths = spec["paths"]
    expected = {
        "/api/v1/deals": {"get", "post"},
        "/api/v1/deals/{code}": {"get", "patch", "delete"},
        "/api/v1/deals/{code}/history": {"get"},
        "/api/v1/deals/{code}/changes": {"post"},
        "/api/v1/deals/{code}/deletion-impact": {"get"},
    }
    # then: 메서드 집합과 태그가 맞고 옛 경로는 없다
    for path, methods in expected.items():
        assert set(paths[path]) == methods, path
        assert all(op["tags"] == ["deals"] for op in paths[path].values()), path
    retired = {
        "/api/v1/deals/{deal_id}",
        "/api/v1/deals/by-code/{code}",
        "/api/v1/deals/{deal_id}/stage",
        "/api/v1/deals/{deal_id}/stage-changes",
        "/api/v1/deals/pipeline",
        "/api/v1/deals/facets",
        "/api/v1/vendors/{vendor_id}/solutions",
        "/api/v1/vendors/{vendor_id}/solutions/{solution_id}",
    }
    assert not retired & set(paths)


def test_deal_delete_documents_the_confirm_code_and_error_responses(spec: Spec) -> None:
    """Deal 삭제는 confirm_code 필수 쿼리와 204·403·404·422 응답을 문서화한다."""
    # when: Deal 삭제 오퍼레이션을 읽는다
    operation = operation_of(spec, "DELETE", "/api/v1/deals/{code}")
    # then: confirm_code는 필수 쿼리이고 204·403·404·422 응답이 있다
    params = {p["name"]: p for p in operation["parameters"]}
    assert params["confirm_code"]["required"] is True
    assert {"204", "403", "404", "422"} <= set(operation["responses"])


def test_user_response_has_exactly_the_documented_fields_and_no_password(spec: Spec) -> None:
    """사용자 응답은 문서화된 필드만 갖고 비밀번호 필드는 없다."""
    # when: 사용자 등록의 응답 스키마를 읽는다
    schema = _response_schema(spec, operation_of(spec, "POST", "/api/v1/users"))
    # then: 속성이 문서화된 필드와 정확히 같고 비밀번호 필드는 없다
    assert set(schema["properties"]) == {
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


def test_every_user_display_in_responses_uses_user_ref(spec: Spec) -> None:
    """응답에서 사용자를 보여 주는 필드는 UserRef 스키마를 쓴다."""
    # when: 응답 스키마의 사용자 표시 필드를 읽는다
    schemas = spec["components"]["schemas"]
    # then: 모든 필드가 UserRef를 참조한다
    for schema, field in USER_REF_FIELDS:
        assert "UserRef" in str(schemas[schema]["properties"][field]), (schema, field)


def test_users_list_documents_the_status_filter_with_active_as_default(spec: Spec) -> None:
    """사용자 목록은 상태 필터(active·resigned·all)를 문서화하고 기본값은 active다."""
    # when: 사용자 목록의 status 파라미터를 읽는다
    status = _params(spec, "/api/v1/users")["status"]
    # then: enum은 active·resigned·all이고 기본값 active, 필수가 아니다
    assert set(status["schema"]["enum"]) == {"active", "resigned", "all"}
    assert status["schema"]["default"] == "active"
    assert not status.get("required")


def test_users_list_is_a_page_of_user_responses(spec: Spec) -> None:
    """사용자 목록 응답은 items·offset·limit을 가진 페이지다."""
    # when: 사용자 목록의 응답 스키마를 읽는다
    schema = _response_schema(spec, operation_of(spec, "GET", "/api/v1/users"))
    # then: 속성이 items·offset·limit뿐이다
    assert set(schema["properties"]) == {"items", "offset", "limit"}


def test_user_delete_documents_the_outcome_the_reason_query_and_errors(spec: Spec) -> None:
    """사용자 삭제는 200 결과(deleted·resigned), reason 쿼리, 오류 응답을 문서화한다."""
    # when: 사용자 삭제 오퍼레이션을 읽는다
    operation = operation_of(spec, "DELETE", "/api/v1/users/{user_id}")
    # then: 200과 오류 응답이 있고 outcome은 deleted·resigned, reason은 기본 resigned 쿼리다
    assert "204" not in operation["responses"]
    assert {"200", "401", "403", "404", "409", "422"} <= set(operation["responses"])
    body = _response_schema(spec, operation)
    assert set(body["properties"]) == {"outcome"}
    assert set(body["properties"]["outcome"]["enum"]) == {"deleted", "resigned"}
    reason = next(p for p in operation["parameters"] if p["name"] == "reason")
    assert (reason["in"], reason["schema"]["enum"], reason["schema"]["default"]) == (
        "query",
        ["resigned"],
        "resigned",
    )


def test_user_options_document_the_filters_and_only_user_ref_items(spec: Spec) -> None:
    """사용자 선택 목록은 필터를 문서화하고 UserRef 항목만 공개한다."""
    # when: 사용자 선택 목록 오퍼레이션을 읽는다
    operation = operation_of(spec, "GET", "/api/v1/user-options")
    params = {p["name"]: p for p in operation["parameters"]}
    page = _response_schema(spec, operation)
    # then: 필터 파라미터가 있고 limit은 없으며 항목은 UserRef, 401·422 응답이 있다
    assert {"include_resigned", "keyword", "role"} <= set(params)
    assert "limit" not in params
    assert params["include_resigned"]["schema"]["default"] is False
    assert "UserRef" in str(page["properties"]["items"])
    assert {"401", "422"} <= set(operation["responses"])


def test_auth_me_response_documents_the_user_id(spec: Spec) -> None:
    """내 정보 응답은 user_id 필드를 문서화한다."""
    # when: 내 정보 응답 스키마를 읽는다
    schema = _response_schema(spec, operation_of(spec, "GET", "/api/v1/auth/me"))
    # then: user_id 속성이 있다
    assert "user_id" in schema["properties"]


def test_login_allows_only_post(spec: Spec) -> None:
    """로그인 경로는 POST만 공개한다."""
    # when: 로그인 경로의 메서드를 읽는다
    methods = set(spec["paths"]["/api/v1/auth/login"])
    # then: post뿐이다
    assert methods == {"post"}
