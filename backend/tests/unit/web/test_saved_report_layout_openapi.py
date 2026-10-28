"""저장 리포트 결과 배치 OpenAPI 계약 (AC24~27): 요청 layout, 응답 layout, 배치 저장 경로.

스키마 이름은 구현이 정하므로 `$ref`를 따라가서 필드 구성만 본다. 기존 경로·필드는 그대로다.
"""

from typing import Any

import pytest

from app.domain.common.ids import MAX_ID
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BASE = "/api/v1/reports"
ID_ROUTE = f"{BASE}/{{report_id}}"
LAYOUT_ROUTE = f"{ID_ROUTE}/layout"
LAYOUT_KEYS = {"view", "order", "arrange"}
VIEWS = {"both", "chart", "table"}
ARRANGES = {"side_by_side", "stacked"}
TILES = {"table", "chart"}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["components"]["schemas"][node["$ref"].rsplit("/", 1)[1]]
    return node


def _non_null(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    if "anyOf" in node:
        (inner,) = [n for n in node["anyOf"] if n.get("type") != "null"]
        return _resolve(schema, inner)
    return _resolve(schema, node)


def _is_nullable(node: dict[str, Any]) -> bool:
    return any(n.get("type") == "null" for n in node.get("anyOf", []))


def _body(schema: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    body = schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    return _resolve(schema, body)


def _response(schema: dict[str, Any], method: str, path: str, code: str) -> dict[str, Any]:
    content = schema["paths"][path][method]["responses"][code]["content"]["application/json"]
    return _resolve(schema, content["schema"])


def _enum(schema: dict[str, Any], node: dict[str, Any]) -> set[str]:
    return set(_non_null(schema, node)["enum"])


def test_layout_route_documents_403_404_409_422(schema: dict[str, Any]) -> None:
    assert set(schema["paths"][LAYOUT_ROUTE]) == {"put"}
    responses = schema["paths"][LAYOUT_ROUTE]["put"]["responses"]

    assert {"200", "401", "403", "404", "409", "422"} <= set(responses)


def test_layout_route_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    (param,) = [
        p for p in schema["paths"][LAYOUT_ROUTE]["put"]["parameters"] if p["name"] == "report_id"
    ]

    assert param["schema"]["type"] == "integer"
    assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)


def test_layout_request_has_layout_and_a_revision_of_at_least_one(schema: dict[str, Any]) -> None:
    body = _body(schema, "put", LAYOUT_ROUTE)

    assert set(body["properties"]) == {"layout", "revision"}
    assert set(body["required"]) == {"layout", "revision"}
    assert body["properties"]["revision"]["type"] == "integer"
    assert body["properties"]["revision"]["minimum"] == 1
    assert body.get("additionalProperties") is False


def test_layout_request_object_requires_the_three_keys_and_forbids_unknown_ones(
    schema: dict[str, Any],
) -> None:
    layout = _non_null(schema, _body(schema, "put", LAYOUT_ROUTE)["properties"]["layout"])

    assert set(layout["properties"]) == LAYOUT_KEYS
    assert set(layout["required"]) == LAYOUT_KEYS
    assert layout.get("additionalProperties") is False


@pytest.mark.parametrize("method", ["post", "put"])
def test_create_update_request_layout_optional(schema: dict[str, Any], method: str) -> None:
    path = BASE if method == "post" else ID_ROUTE
    body = _body(schema, method, path)

    assert "layout" in body["properties"]
    assert "layout" not in body["required"]
    assert _is_nullable(body["properties"]["layout"])
    layout = _non_null(schema, body["properties"]["layout"])
    assert set(layout["properties"]) == LAYOUT_KEYS


def test_copy_request_has_no_layout(schema: dict[str, Any]) -> None:
    assert "layout" not in _body(schema, "post", f"{ID_ROUTE}/copy")["properties"]


@pytest.mark.parametrize(
    ("method", "path", "code"),
    [
        ("post", BASE, "201"),
        ("get", ID_ROUTE, "200"),
        ("put", ID_ROUTE, "200"),
        ("post", f"{ID_ROUTE}/copy", "201"),
        ("put", LAYOUT_ROUTE, "200"),
    ],
)
def test_detail_response_requires_layout(
    schema: dict[str, Any], method: str, path: str, code: str
) -> None:
    detail = _response(schema, method, path, code)

    assert "layout" in detail["properties"]
    assert "layout" in detail["required"]
    assert not _is_nullable(detail["properties"]["layout"])
    layout = _resolve(schema, detail["properties"]["layout"])
    assert set(layout["properties"]) == LAYOUT_KEYS
    assert set(layout["required"]) == LAYOUT_KEYS


def test_layout_response_enums_and_order_length(schema: dict[str, Any]) -> None:
    detail = _response(schema, "get", ID_ROUTE, "200")
    layout = _resolve(schema, detail["properties"]["layout"])
    order = layout["properties"]["order"]

    assert _enum(schema, layout["properties"]["view"]) == VIEWS
    assert _enum(schema, layout["properties"]["arrange"]) == ARRANGES
    assert order["type"] == "array"
    assert _enum(schema, order["items"]) == TILES
    assert (order.get("minItems"), order.get("maxItems")) == (2, 2)


def test_list_items_do_not_carry_the_layout(schema: dict[str, Any]) -> None:
    listing = _response(schema, "get", BASE, "200")
    item = _resolve(schema, listing["items"])

    assert "layout" not in item["properties"]


def test_the_existing_report_routes_keep_their_methods(schema: dict[str, Any]) -> None:
    paths = schema["paths"]

    assert set(paths[BASE]) == {"get", "post"}
    assert set(paths[ID_ROUTE]) == {"get", "put", "delete"}
    assert set(paths[f"{ID_ROUTE}/copy"]) == {"post"}
    assert set(paths[f"{ID_ROUTE}/run"]) == {"post"}
