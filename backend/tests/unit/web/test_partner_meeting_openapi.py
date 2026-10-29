"""파트너 미팅 API의 OpenAPI 계약: 경로·메서드, 응답 코드, 요청·응답 필드, 태그."""

from typing import Any

import pytest

from app.domain.common.ids import MAX_ID
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BASE = "/api/v1/partner-meetings"
ID_ROUTE = f"{BASE}/{{meeting_id}}"
OPTIONS = f"{BASE}/deal-options"
ITEM_FIELDS = {"partner_company", "deal_code", "meeting_date", "content"}
RESPONSE_FIELDS = {
    "id",
    "partner_company",
    "deal",
    "meeting_date",
    "content",
    "author",
    "created_at",
    "updated_at",
}


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


def test_paths_and_methods(schema: dict[str, Any]) -> None:
    paths = schema["paths"]

    assert set(paths[BASE]) == {"get", "post"}
    assert set(paths[ID_ROUTE]) == {"put", "delete"}
    assert set(paths[OPTIONS]) == {"get"}


def test_every_operation_is_tagged_partner_meetings(schema: dict[str, Any]) -> None:
    for path in (BASE, ID_ROUTE, OPTIONS):
        for operation in schema["paths"][path].values():
            assert operation["tags"] == ["partner-meetings"], path


@pytest.mark.parametrize(
    ("method", "path", "success"),
    [
        ("get", BASE, "200"),
        ("post", BASE, "201"),
        ("put", ID_ROUTE, "200"),
        ("delete", ID_ROUTE, "204"),
        ("get", OPTIONS, "200"),
    ],
)
def test_success_status_codes_and_401(
    schema: dict[str, Any], method: str, path: str, success: str
) -> None:
    responses = schema["paths"][path][method]["responses"]

    assert success in responses
    assert "401" in responses


@pytest.mark.parametrize(
    ("method", "path", "codes"),
    [
        ("get", BASE, {"422"}),
        ("post", BASE, {"403", "422"}),
        ("put", ID_ROUTE, {"403", "404", "422"}),
        ("delete", ID_ROUTE, {"403", "404", "422"}),
        ("get", OPTIONS, {"422"}),
    ],
)
def test_error_status_codes_are_documented(
    schema: dict[str, Any], method: str, path: str, codes: set[str]
) -> None:
    assert codes <= set(schema["paths"][path][method]["responses"])


def test_reads_document_no_403(schema: dict[str, Any]) -> None:
    assert "403" not in schema["paths"][BASE]["get"]["responses"]  # 모든 역할이 읽는다
    assert "403" not in schema["paths"][OPTIONS]["get"]["responses"]


def test_meeting_id_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    for method in ("put", "delete"):
        (param,) = [
            p for p in schema["paths"][ID_ROUTE][method]["parameters"] if p["name"] == "meeting_id"
        ]
        assert param["schema"]["type"] == "integer"
        assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)


def test_list_query_parameters(schema: dict[str, Any]) -> None:
    params = {p["name"]: p for p in schema["paths"][BASE]["get"]["parameters"]}

    assert set(params) == {
        "partner",
        "deal",
        "content",
        "date_from",
        "date_to",
        "author_user_id",
        "sort",
        "order",
        "offset",
        "limit",
    }
    assert params["limit"]["schema"]["default"] == 10
    assert params["limit"]["schema"]["maximum"] == 200
    assert params["offset"]["schema"]["minimum"] == 0
    assert not any(p["required"] for p in params.values())


def _enum(schema: dict[str, Any], node: dict[str, Any]) -> set[str]:
    resolved = _resolve(schema, node)
    found = set(resolved.get("enum", []))
    for option in resolved.get("anyOf", []):
        found |= _enum(schema, option)
    return found


def test_the_sort_and_order_parameters_list_their_values(schema: dict[str, Any]) -> None:
    params = {p["name"]: p["schema"] for p in schema["paths"][BASE]["get"]["parameters"]}

    assert _enum(schema, params["sort"]) == {"meeting_date", "partner", "deal", "content", "author"}
    assert _enum(schema, params["order"]) == {"asc", "desc"}


def test_text_filters_document_their_max_lengths(schema: dict[str, Any]) -> None:
    params = {p["name"]: p["schema"] for p in schema["paths"][BASE]["get"]["parameters"]}

    def max_length(node: dict[str, Any]) -> int:
        options = [node, *node.get("anyOf", [])]
        return int(next(o["maxLength"] for o in options if "maxLength" in o))

    assert max_length(params["partner"]) == 200
    assert max_length(params["deal"]) == 200
    assert max_length(params["content"]) == 100


def test_create_body_is_a_list_of_one_to_fifty_items(schema: dict[str, Any]) -> None:
    body = _body(schema, "post", BASE)
    items = body["properties"]["items"]
    item = _resolve(schema, items["items"])

    assert set(body["properties"]) == {"items"}
    assert body["required"] == ["items"]
    assert (items["minItems"], items["maxItems"]) == (1, 50)
    assert set(item["properties"]) == ITEM_FIELDS
    assert set(item["required"]) == ITEM_FIELDS
    assert item["additionalProperties"] is False


def test_update_body_is_one_item(schema: dict[str, Any]) -> None:
    body = _body(schema, "put", ID_ROUTE)

    assert set(body["properties"]) == ITEM_FIELDS
    assert body["additionalProperties"] is False


def test_item_field_lengths_are_documented(schema: dict[str, Any]) -> None:
    properties = _body(schema, "put", ID_ROUTE)["properties"]

    assert properties["partner_company"]["maxLength"] == 200
    assert properties["deal_code"]["maxLength"] == 50
    assert properties["meeting_date"]["format"] == "date"


def test_list_response_is_a_counted_page_of_meetings(schema: dict[str, Any]) -> None:
    page = _response(schema, "get", BASE, "200")
    item = _resolve(schema, page["properties"]["items"]["items"])

    assert set(page["properties"]) == {"items", "total", "offset", "limit"}
    assert set(item["properties"]) == RESPONSE_FIELDS


def test_create_response_wraps_the_created_items(schema: dict[str, Any]) -> None:
    body = _response(schema, "post", BASE, "201")
    item = _resolve(schema, body["properties"]["items"]["items"])

    assert set(body["properties"]) == {"items"}
    assert set(item["properties"]) == RESPONSE_FIELDS


def test_update_response_is_one_meeting(schema: dict[str, Any]) -> None:
    assert set(_response(schema, "put", ID_ROUTE, "200")["properties"]) == RESPONSE_FIELDS


def test_user_columns_use_the_shared_user_ref_schema(schema: dict[str, Any]) -> None:
    item = _response(schema, "put", ID_ROUTE, "200")

    assert item["properties"]["author"]["$ref"].endswith("/UserRef")


def test_deal_options_response_lists_code_name_and_customer_company(
    schema: dict[str, Any],
) -> None:
    body = _response(schema, "get", OPTIONS, "200")
    option = _resolve(schema, body["properties"]["items"]["items"])
    company = {p["name"]: p for p in schema["paths"][OPTIONS]["get"]["parameters"]}["company"]

    assert set(option["properties"]) == {"code", "name", "customer_company"}
    assert company["required"] is True


def test_the_deletion_impact_response_has_the_partner_meeting_count(
    schema: dict[str, Any],
) -> None:
    impact = _response(schema, "get", "/api/v1/deals/{code}/deletion-impact", "200")

    assert "partner_meeting_count" in impact["properties"]
    assert "partner_meeting_count" in impact["required"]
    assert impact["properties"]["partner_meeting_count"]["type"] == "integer"
