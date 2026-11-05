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
    paths = schema["paths"]

    assert set(paths[BASE]) == {"get"}
    assert set(paths[ID_ROUTE]) == {"get", "put", "delete"}
    assert set(paths[ISSUE]) == {"post"}
    assert set(paths[RENEWAL]) == {"post"}
    assert set(paths[END]) == {"post"}
    assert set(paths[FILES]) == {"get", "post"}
    assert set(paths[FILE_ROUTE]) == {"delete"}
    assert set(paths[DOWNLOAD]) == {"get"}


def test_there_is_no_manual_create_route(schema: dict[str, Any]) -> None:
    assert "post" not in schema["paths"][BASE]  # 계약은 Won이 될 때 자동으로만 생긴다


def test_every_operation_is_tagged(schema: dict[str, Any]) -> None:
    for path in (BASE, ID_ROUTE, ISSUE, RENEWAL, END, FILES):
        for operation in schema["paths"][path].values():
            assert operation["tags"] == ["license-contracts"], path
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
    responses = schema["paths"][path][method]["responses"]

    assert success in responses
    assert "401" in responses


def test_the_attachment_upload_also_documents_the_200_for_replaced_and_skipped(
    schema: dict[str, Any],
) -> None:
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
    assert codes <= set(schema["paths"][path][method]["responses"])


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", BASE), ("get", ID_ROUTE), ("get", FILES), ("get", DOWNLOAD)],
)
def test_reads_document_no_403(schema: dict[str, Any], method: str, path: str) -> None:
    assert "403" not in schema["paths"][path][method]["responses"]  # 모든 역할이 읽는다


def test_the_contract_id_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    for method in ("get", "put", "delete"):
        (param,) = [
            p for p in schema["paths"][ID_ROUTE][method]["parameters"] if p["name"] == "contract_id"
        ]
        assert param["schema"]["type"] == "integer"
        assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)


def test_list_query_parameters(schema: dict[str, Any]) -> None:
    params = {p["name"]: p for p in schema["paths"][BASE]["get"]["parameters"]}

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
    params = {p["name"]: p["schema"] for p in schema["paths"][BASE]["get"]["parameters"]}

    assert _enum(schema, params["sort"]) == {
        "deal_code",
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
    body = _body(schema, "put", ID_ROUTE)

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
    body = _body(schema, "post", path)

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
    for method, path, code in (
        ("get", ID_ROUTE, "200"),
        ("put", ID_ROUTE, "200"),
        ("post", ISSUE, "200"),
        ("post", RENEWAL, "201"),
        ("post", END, "200"),
    ):
        assert set(_response(schema, method, path, code)["properties"]) == RESPONSE_FIELDS, path


def test_the_list_response_is_a_counted_page_of_contracts(schema: dict[str, Any]) -> None:
    page = _response(schema, "get", BASE, "200")
    item = _resolve(schema, page["properties"]["items"]["items"])

    assert set(page["properties"]) == {"items", "total", "offset", "limit"}
    assert set(item["properties"]) == RESPONSE_FIELDS


def test_ids_and_user_columns_use_the_shared_schemas(schema: dict[str, Any]) -> None:
    item = _response(schema, "get", ID_ROUTE, "200")["properties"]

    assert item["id"]["type"] == "integer"
    assert item["sales_owner"]["$ref"].endswith("/UserRef")
    assert item["created_by"]["$ref"].endswith("/UserRef")
    assert item["updated_by"]["$ref"].endswith("/UserRef")


def test_the_deal_requests_document_the_optional_delete_flag(schema: dict[str, Any]) -> None:
    patch = _body(schema, "patch", "/api/v1/deals/{code}")
    change = _body(schema, "post", "/api/v1/deals/{code}/changes")
    action = _body(schema, "post", "/api/v1/deals/{code}/actions")

    for body in (patch, change, action):
        flag = body["properties"]["delete_license_contracts"]
        assert flag["type"] == "boolean"
        assert flag["default"] is False
        assert "delete_license_contracts" not in body.get("required", [])


def test_the_deal_create_request_has_no_delete_flag(schema: dict[str, Any]) -> None:
    create = _body(schema, "post", "/api/v1/deals")

    assert "delete_license_contracts" not in create["properties"]


def test_deal_responses_document_the_contract_count(schema: dict[str, Any]) -> None:
    detail = _response(schema, "get", "/api/v1/deals/{code}", "200")
    impact = _response(schema, "get", "/api/v1/deals/{code}/deletion-impact", "200")

    assert detail["properties"]["license_contract_count"]["type"] == "integer"
    assert "license_contract_count" in detail["required"]
    assert impact["properties"]["license_contract_count"]["type"] == "integer"
    assert "license_contract_count" in impact["required"]


def test_deal_and_contract_responses_have_issued_and_won_flags(schema: dict[str, Any]) -> None:
    detail = _response(schema, "get", "/api/v1/deals/{code}", "200")
    contract = _response(schema, "get", ID_ROUTE, "200")

    assert detail["properties"]["has_issued_license_contract"]["type"] == "boolean"
    assert "has_issued_license_contract" in detail["required"]
    assert contract["properties"]["deal_is_won"]["type"] == "boolean"
    assert "deal_is_won" in contract["required"]


def test_deal_list_rows_document_the_issued_flag(schema: dict[str, Any]) -> None:
    page = _response(schema, "get", "/api/v1/deals", "200")
    row = _resolve(schema, page["properties"]["items"]["items"])

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
    assert "409" in schema["paths"][path][method]["responses"]  # 발급 계약이 있는 Won 이탈 거부
