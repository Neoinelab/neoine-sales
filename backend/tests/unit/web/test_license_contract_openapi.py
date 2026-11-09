"""계약 API의 OpenAPI 계약(AC16·D12): 경로·메서드, 응답 코드, 요청·응답 필드, 태그."""

from typing import Any

import pytest

from app.domain.common.ids import MAX_ID
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BASE = "/api/v1/license-contracts"
ID_ROUTE = f"{BASE}/{{contract_id}}"
ISSUE = f"{ID_ROUTE}/issue"
RENEWAL = f"{ID_ROUTE}/renewal"
END = f"{ID_ROUTE}/end"
FILES = f"{ID_ROUTE}/attachments"
FILE_ROUTE = "/api/v1/license-contract-attachments/{attachment_id}"
DOWNLOAD = f"{FILE_ROUTE}/download"
RESPONSE_FIELDS = {
    "id",
    "deal_code",
    "deal_name",
    "customer",
    "vendor",
    "product",
    "partner",
    "sales_owner",
    "status",
    "license_start",
    "license_end",
    "term",
    "tech_owner",
    "inspection_cycle",
    "note",
    "renewed_from_id",
    "ended_at",
    "attachment_count",
    "deal_is_won",
    "created_by",
    "updated_by",
    "created_at",
    "updated_at",
}
FIELDS_BODY = {"tech_owner", "inspection_cycle", "note"}
ISSUE_BODY = {*FIELDS_BODY, "start_date", "term_amount", "term_unit"}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["components"]["schemas"][node["$ref"].rsplit("/", 1)[1]]
    return node


def _body(schema: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    body = schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    return _resolve(schema, body)


def _response(schema: dict[str, Any], method: str, path: str, code: str) -> dict[str, Any]:
    content = schema["paths"][path][method]["responses"][code]["content"]["application/json"]
    return _resolve(schema, content["schema"])


def _enum(schema: dict[str, Any], node: dict[str, Any]) -> set[str]:
    resolved = _resolve(schema, node)
    found = set(resolved.get("enum", []))
    for option in resolved.get("anyOf", []):
        found |= _enum(schema, option)
    return found


def test_paths_and_methods(schema: dict[str, Any]) -> None:
    """계약 API는 문서화된 경로와 메서드를 가진다."""
    # given: 앱의 OpenAPI 스키마
    # when: 경로별 메서드를 모은다
    paths = schema["paths"]

    # then: 목록·상세·발급·갱신·종료·첨부·다운로드 메서드가 명세와 같다
    assert set(paths[BASE]) == {"get"}
    assert set(paths[ID_ROUTE]) == {"get", "put", "delete"}
    assert set(paths[ISSUE]) == {"post"}
    assert set(paths[RENEWAL]) == {"post"}
    assert set(paths[END]) == {"post"}
    assert set(paths[FILES]) == {"get", "post"}
    assert set(paths[FILE_ROUTE]) == {"delete"}
    assert set(paths[DOWNLOAD]) == {"get"}


def test_there_is_no_manual_create_route(schema: dict[str, Any]) -> None:
    """계약을 직접 만드는 POST 경로는 없다."""
    # given: 앱의 OpenAPI 스키마
    # when: 목록 경로의 메서드를 본다
    # then: post가 없다
    assert "post" not in schema["paths"][BASE]  # 계약은 Won이 될 때 자동으로만 생긴다


def test_every_operation_is_tagged(schema: dict[str, Any]) -> None:
    """모든 동작에 태그가 붙어 있다."""
    # given: 앱의 OpenAPI 스키마
    # when: 각 경로의 동작 태그를 본다
    for path in (BASE, ID_ROUTE, ISSUE, RENEWAL, END, FILES):
        for operation in schema["paths"][path].values():
            assert operation["tags"] == ["license-contracts"], path
    # then: 계약 경로는 license-contracts, 첨부 경로는 license-contract-attachments
    for path in (FILE_ROUTE, DOWNLOAD):
        for operation in schema["paths"][path].values():
            assert operation["tags"] == ["license-contract-attachments"], path


@pytest.mark.parametrize(
    ("method", "path", "success"),
    [
        ("get", BASE, "200"),
        ("get", ID_ROUTE, "200"),
        ("put", ID_ROUTE, "200"),
        ("delete", ID_ROUTE, "204"),
        ("post", ISSUE, "200"),
        ("post", RENEWAL, "201"),
        ("post", END, "200"),
        ("get", FILES, "200"),
        ("post", FILES, "201"),
        ("delete", FILE_ROUTE, "204"),
        ("get", DOWNLOAD, "200"),
    ],
)
def test_success_status_codes_and_401(
    schema: dict[str, Any], method: str, path: str, success: str
) -> None:
    """각 동작은 성공 코드와 401을 문서화한다."""
    # given: 앱의 OpenAPI 스키마
    # when: 동작의 응답 코드를 본다
    responses = schema["paths"][path][method]["responses"]

    # then: 성공 코드와 401이 있다
    assert success in responses
    assert "401" in responses


def test_the_attachment_upload_also_documents_the_200_for_replaced_and_skipped(
    schema: dict[str, Any],
) -> None:
    """첨부 업로드는 교체·건너뜀의 200도 문서화한다.

    테스트 코드: LC-065, LC-066
    """
    # given: 앱의 OpenAPI 스키마
    # when: 업로드 응답 코드를 본다
    # then: 200이 있다
    assert "200" in schema["paths"][FILES]["post"]["responses"]


@pytest.mark.parametrize(
    ("method", "path", "codes"),
    [
        ("get", BASE, {"422"}),
        ("get", ID_ROUTE, {"404"}),
        ("put", ID_ROUTE, {"403", "404", "422"}),
        ("delete", ID_ROUTE, {"403", "404"}),
        ("post", ISSUE, {"403", "404", "409", "422"}),
        ("post", RENEWAL, {"403", "404", "409", "422"}),
        ("post", END, {"403", "404", "409"}),
        ("get", FILES, {"404"}),
        ("post", FILES, {"403", "404", "409", "422", "503"}),
        ("delete", FILE_ROUTE, {"403", "404"}),
        ("get", DOWNLOAD, {"404", "503"}),
    ],
)
def test_error_status_codes_are_documented_and_mutations_document_403(
    schema: dict[str, Any], method: str, path: str, codes: set[str]
) -> None:
    """오류 코드와 쓰기 동작의 403이 문서화된다(삭제는 403·404 모두).

    테스트 코드: LC-083
    """
    # given: 앱의 OpenAPI 스키마
    # when: 동작의 응답 코드를 본다
    # then: 기대한 오류 코드가 모두 있다
    assert codes <= set(schema["paths"][path][method]["responses"])


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", BASE), ("get", ID_ROUTE), ("get", FILES), ("get", DOWNLOAD)],
)
def test_reads_document_no_403(schema: dict[str, Any], method: str, path: str) -> None:
    """읽기 동작은 403을 문서화하지 않는다.

    테스트 코드: LC-082
    """
    # given: 앱의 OpenAPI 스키마
    # when: 읽기 동작의 응답 코드를 본다
    # then: 403이 없다
    assert "403" not in schema["paths"][path][method]["responses"]  # 모든 역할이 읽는다


def test_the_contract_id_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    """계약 id 경로 파라미터는 1~2^53-1 정수다."""
    # given: 앱의 OpenAPI 스키마
    # when: id 경로 파라미터를 본다
    for method in ("get", "put", "delete"):
        (param,) = [
            p for p in schema["paths"][ID_ROUTE][method]["parameters"] if p["name"] == "contract_id"
        ]
        assert param["schema"]["type"] == "integer"
        assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)
    # then: 정수, 최소 1, 최대 MAX_ID


def test_list_query_parameters(schema: dict[str, Any]) -> None:
    """목록 쿼리 파라미터는 명세의 13개이고 모두 선택이다.

    테스트 코드: LC-019
    """
    # given: 앱의 OpenAPI 스키마
    # when: 목록 파라미터를 모은다
    params = {p["name"]: p for p in schema["paths"][BASE]["get"]["parameters"]}

    # then: 이름 13개, limit 기본 50·최대 200, offset 최소 0, 필수 없음
    assert set(params) == {
        "customer",
        "product",
        "vendor_id",
        "owner_user_id",
        "status",
        "start_from",
        "start_to",
        "end_from",
        "end_to",
        "sort",
        "order",
        "offset",
        "limit",
    }
    assert params["limit"]["schema"]["default"] == 50
    assert params["limit"]["schema"]["maximum"] == 200
    assert params["offset"]["schema"]["minimum"] == 0
    assert not any(p["required"] for p in params.values())


def test_the_sort_status_and_order_parameters_list_their_values(schema: dict[str, Any]) -> None:
    """정렬은 12개 키이고 deal_code가 없으며 상태·방향 값이 문서화된다.

    테스트 코드: LC-021, LC-084
    """
    # given: 앱의 OpenAPI 스키마
    # when: sort·status·order 파라미터의 값을 모은다
    params = {p["name"]: p["schema"] for p in schema["paths"][BASE]["get"]["parameters"]}

    # then: sort 12개, status 4개, order asc·desc
    assert _enum(schema, params["sort"]) == {
        "deal_name",
        "customer",
        "vendor",
        "product",
        "partner",
        "license_start",
        "license_end",
        "status",
        "sales_owner",
        "tech_owner",
        "inspection",
        "note",
    }
    assert _enum(schema, params["status"]) == {
        "not_issued",
        "issued_new",
        "issued_renewal",
        "ended",
    }
    assert _enum(schema, params["order"]) == {"asc", "desc"}


def test_the_fields_body_has_the_three_contract_columns_and_forbids_extras(
    schema: dict[str, Any],
) -> None:
    """계약 칸 요청 본문은 세 칸뿐이고 추가 필드를 금지한다.

    테스트 코드: LC-033
    """
    # given: 앱의 OpenAPI 스키마
    # when: PUT 요청 본문 스키마를 본다
    body = _body(schema, "put", ID_ROUTE)

    # then: 세 칸, additionalProperties false, 기술담당 최대 100
    assert set(body["properties"]) == FIELDS_BODY
    assert body["additionalProperties"] is False
    assert body["properties"]["tech_owner"]["maxLength"] == 100
    assert _enum(schema, body["properties"]["inspection_cycle"]) == {
        "monthly",
        "quarterly",
        "semiannual",
        "yearly",
        "none",
    }


@pytest.mark.parametrize("path", [ISSUE, RENEWAL])
def test_the_issue_and_renewal_bodies_add_the_period(schema: dict[str, Any], path: str) -> None:
    """발급·갱신 본문은 계약 칸에 시작일·수량·단위를 더한다.

    테스트 코드: LC-044
    """
    # given: 앱의 OpenAPI 스키마
    # when: 요청 본문 스키마를 본다
    body = _body(schema, "post", path)

    # then: 필드와 필수, 수량 1~99, 단위 month·year
    assert set(body["properties"]) == ISSUE_BODY
    assert {"start_date", "term_amount", "term_unit"} <= set(body["required"])
    assert body["additionalProperties"] is False
    assert body["properties"]["start_date"]["format"] == "date"
    assert (
        body["properties"]["term_amount"]["minimum"],
        body["properties"]["term_amount"]["maximum"],
    ) == (1, 99)
    assert _enum(schema, body["properties"]["term_unit"]) == {"month", "year"}


def test_the_contract_response_has_the_documented_fields(schema: dict[str, Any]) -> None:
    """계약 응답은 문서화된 필드를 가진다.

    테스트 코드: LC-028
    """
    # given: 앱의 OpenAPI 스키마
    # when: 상세·수정·발급·갱신·종료의 응답 스키마를 본다
    for method, path, code in (
        ("get", ID_ROUTE, "200"),
        ("put", ID_ROUTE, "200"),
        ("post", ISSUE, "200"),
        ("post", RENEWAL, "201"),
        ("post", END, "200"),
    ):
        assert set(_response(schema, method, path, code)["properties"]) == RESPONSE_FIELDS, path
    # then: 필드 집합이 명세와 같다


def test_the_list_response_is_a_counted_page_of_contracts(schema: dict[str, Any]) -> None:
    """목록 응답은 계약의 개수가 있는 쪽이다.

    테스트 코드: LC-016
    """
    # given: 앱의 OpenAPI 스키마
    # when: 목록 응답 스키마를 본다
    page = _response(schema, "get", BASE, "200")
    item = _resolve(schema, page["properties"]["items"]["items"])

    # then: items·total·offset·limit과 항목 필드가 명세와 같다
    assert set(page["properties"]) == {"items", "total", "offset", "limit"}
    assert set(item["properties"]) == RESPONSE_FIELDS


def test_ids_and_user_columns_use_the_shared_schemas(schema: dict[str, Any]) -> None:
    """id는 정수이고 사용자 칸은 공용 UserRef 스키마를 쓴다."""
    # given: 앱의 OpenAPI 스키마
    # when: 상세 응답 스키마를 본다
    item = _response(schema, "get", ID_ROUTE, "200")["properties"]

    # then: id 정수, sales_owner·created_by·updated_by는 UserRef
    assert item["id"]["type"] == "integer"
    assert item["sales_owner"]["$ref"].endswith("/UserRef")
    assert item["created_by"]["$ref"].endswith("/UserRef")
    assert item["updated_by"]["$ref"].endswith("/UserRef")


def test_the_deal_requests_document_the_optional_delete_flag(schema: dict[str, Any]) -> None:
    """Deal 변경 세 요청은 선택 삭제 값(기본 false)을 문서화한다.

    테스트 코드: LC-007
    """
    # given: 앱의 OpenAPI 스키마
    # when: 수정·변경·Action 요청 본문을 본다
    patch = _body(schema, "patch", "/api/v1/deals/{code}")
    change = _body(schema, "post", "/api/v1/deals/{code}/changes")
    action = _body(schema, "post", "/api/v1/deals/{code}/actions")

    # then: boolean, 기본 false, 필수 아님
    for body in (patch, change, action):
        flag = body["properties"]["delete_license_contracts"]
        assert flag["type"] == "boolean"
        assert flag["default"] is False
        assert "delete_license_contracts" not in body.get("required", [])


def test_the_deal_create_request_has_no_delete_flag(schema: dict[str, Any]) -> None:
    """Deal 등록 요청에는 삭제 값이 없다."""
    # given: 앱의 OpenAPI 스키마
    # when: 등록 요청 본문을 본다
    create = _body(schema, "post", "/api/v1/deals")

    # then: delete_license_contracts가 없다
    assert "delete_license_contracts" not in create["properties"]


def test_deal_responses_document_the_contract_count(schema: dict[str, Any]) -> None:
    """Deal 상세·삭제 영향 응답은 계약 건수를 문서화한다.

    테스트 코드: LC-079
    """
    # given: 앱의 OpenAPI 스키마
    # when: 응답 스키마를 본다
    detail = _response(schema, "get", "/api/v1/deals/{code}", "200")
    impact = _response(schema, "get", "/api/v1/deals/{code}/deletion-impact", "200")

    # then: license_contract_count가 정수이고 필수다
    assert detail["properties"]["license_contract_count"]["type"] == "integer"
    assert "license_contract_count" in detail["required"]
    assert impact["properties"]["license_contract_count"]["type"] == "integer"
    assert "license_contract_count" in impact["required"]


def test_deal_and_contract_responses_have_issued_and_won_flags(schema: dict[str, Any]) -> None:
    """Deal 응답은 발급 여부, 계약 응답은 Won 여부를 문서화한다.

    테스트 코드: LC-030
    """
    # given: 앱의 OpenAPI 스키마
    # when: 응답 스키마를 본다
    detail = _response(schema, "get", "/api/v1/deals/{code}", "200")
    contract = _response(schema, "get", ID_ROUTE, "200")

    # then: has_issued_license_contract·deal_is_won이 boolean이고 필수다
    assert detail["properties"]["has_issued_license_contract"]["type"] == "boolean"
    assert "has_issued_license_contract" in detail["required"]
    assert contract["properties"]["deal_is_won"]["type"] == "boolean"
    assert "deal_is_won" in contract["required"]


def test_deal_list_rows_document_the_issued_flag(schema: dict[str, Any]) -> None:
    """Deal 목록 행은 발급 여부를 문서화한다.

    테스트 코드: LC-030
    """
    # given: 앱의 OpenAPI 스키마
    # when: 목록 응답의 행 스키마를 본다
    page = _response(schema, "get", "/api/v1/deals", "200")
    row = _resolve(schema, page["properties"]["items"]["items"])

    # then: has_issued_license_contract가 boolean이고 필수다
    assert row["properties"]["has_issued_license_contract"]["type"] == "boolean"
    assert "has_issued_license_contract" in row["required"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("patch", "/api/v1/deals/{code}"),
        ("post", "/api/v1/deals/{code}/changes"),
        ("post", "/api/v1/deals/{code}/actions"),
    ],
)
def test_deal_change_routes_document_409(schema: dict[str, Any], method: str, path: str) -> None:
    """Deal 변경 세 경로는 409(발급 계약 Won 이탈 거부)를 문서화한다.

    테스트 코드: LC-008
    """
    # given: 앱의 OpenAPI 스키마
    # when: 세 경로의 응답 코드를 본다
    # then: 409가 있다
    assert "409" in schema["paths"][path][method]["responses"]  # 발급 계약이 있는 Won 이탈 거부
