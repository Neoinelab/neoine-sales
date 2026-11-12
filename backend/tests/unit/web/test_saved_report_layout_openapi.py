"""저장 리포트 결과 배치 OpenAPI 계약: 요청 layout, 응답 layout, 배치 저장 경로.

스키마 이름은 구현이 정하므로 `$ref`를 따라가서 필드 구성만 본다. 기존 경로·필드는 그대로다.
"""

from typing import Any

import pytest

from app.domain.common.ids import MAX_ID
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

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
    """배치 저장 경로는 PUT 하나이고 200·401·403·404·409·422를 문서화한다.

    테스트 코드: RS-052
    """
    # when: 배치 저장 경로의 메서드와 응답 코드를 읽는다
    assert set(schema["paths"][LAYOUT_ROUTE]) == {"put"}
    responses = schema["paths"][LAYOUT_ROUTE]["put"]["responses"]
    # then: 명세의 코드가 모두 있다
    assert {"200", "401", "403", "404", "409", "422"} <= set(responses)


def test_layout_route_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    """배치 저장 경로의 id 파라미터는 1~2^53-1 범위의 정수다.

    테스트 코드: RS-052
    """
    # when: report_id 파라미터를 읽는다
    (param,) = [
        p for p in schema["paths"][LAYOUT_ROUTE]["put"]["parameters"] if p["name"] == "report_id"
    ]
    # then: 정수이고 범위가 1~MAX_ID다
    assert param["schema"]["type"] == "integer"
    assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)


def test_layout_request_has_layout_and_a_revision_of_at_least_one(schema: dict[str, Any]) -> None:
    """배치 저장 요청은 layout·revision(최소 1)만 필수로 갖고 모르는 키를 허용하지 않는다.

    테스트 코드: RS-052
    """
    # when: 배치 저장 요청 스키마를 읽는다
    body = _body(schema, "put", LAYOUT_ROUTE)
    # then: 필드 두 개가 모두 필수이고 revision은 정수 최소 1, 추가 키는 금지다
    assert set(body["properties"]) == {"layout", "revision"}
    assert set(body["required"]) == {"layout", "revision"}
    assert body["properties"]["revision"]["type"] == "integer"
    assert body["properties"]["revision"]["minimum"] == 1
    assert body.get("additionalProperties") is False


def test_layout_request_object_requires_the_three_keys_and_forbids_unknown_ones(
    schema: dict[str, Any],
) -> None:
    """요청의 배치 객체는 세 키가 모두 필수이고 모르는 키를 허용하지 않는다.

    테스트 코드: RS-052
    """
    # when: 요청 배치 객체 스키마를 읽는다
    layout = _non_null(schema, _body(schema, "put", LAYOUT_ROUTE)["properties"]["layout"])
    # then: 세 키가 모두 필수이고 추가 키는 금지다
    assert set(layout["properties"]) == LAYOUT_KEYS
    assert set(layout["required"]) == LAYOUT_KEYS
    assert layout.get("additionalProperties") is False


@pytest.mark.parametrize("method", ["post", "put"])
def test_create_update_request_layout_optional(schema: dict[str, Any], method: str) -> None:
    """만들기·덮어쓰기 요청의 layout은 선택이고 null을 받는다.

    테스트 코드: RS-052
    """
    # when: 요청 스키마를 읽는다
    path = BASE if method == "post" else ID_ROUTE
    body = _body(schema, method, path)
    # then: layout 필드가 있으나 필수가 아니고 nullable이며 세 키를 가진다
    assert "layout" in body["properties"]
    assert "layout" not in body["required"]
    assert _is_nullable(body["properties"]["layout"])
    layout = _non_null(schema, body["properties"]["layout"])
    assert set(layout["properties"]) == LAYOUT_KEYS


def test_copy_request_has_no_layout(schema: dict[str, Any]) -> None:
    """복제 요청에는 layout이 없다.

    테스트 코드: RS-052
    """
    # when: 복제 요청 스키마의 필드를 읽는다
    properties = _body(schema, "post", f"{ID_ROUTE}/copy")["properties"]
    # then: layout 필드가 없다
    assert "layout" not in properties


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
    """상세 응답 5종의 layout은 필수이고 null이 아니며 세 키를 모두 가진다.

    테스트 코드: RS-052
    """
    # when: 상세 응답 스키마를 읽는다
    detail = _response(schema, method, path, code)
    # then: layout이 필수·non-null이고 세 키가 필수다
    assert "layout" in detail["properties"]
    assert "layout" in detail["required"]
    assert not _is_nullable(detail["properties"]["layout"])
    layout = _resolve(schema, detail["properties"]["layout"])
    assert set(layout["properties"]) == LAYOUT_KEYS
    assert set(layout["required"]) == LAYOUT_KEYS


def test_layout_response_enums_and_order_length(schema: dict[str, Any]) -> None:
    """응답 layout의 view·arrange·order 값 집합과 order 길이 2가 명세와 같다.

    테스트 코드: RS-052
    """
    # when: 상세 응답의 layout 스키마를 읽는다
    detail = _response(schema, "get", ID_ROUTE, "200")
    layout = _resolve(schema, detail["properties"]["layout"])
    order = layout["properties"]["order"]
    # then: enum과 order 길이가 명세와 같다
    assert _enum(schema, layout["properties"]["view"]) == VIEWS
    assert _enum(schema, layout["properties"]["arrange"]) == ARRANGES
    assert order["type"] == "array"
    assert _enum(schema, order["items"]) == TILES
    assert (order.get("minItems"), order.get("maxItems")) == (2, 2)


def test_list_items_do_not_carry_the_layout(schema: dict[str, Any]) -> None:
    """목록 항목 스키마에는 layout이 없다.

    테스트 코드: RS-052
    """
    # when: 목록 항목 스키마를 읽는다
    listing = _response(schema, "get", BASE, "200")
    item = _resolve(schema, listing["items"])
    # then: layout 필드가 없다
    assert "layout" not in item["properties"]


def test_the_existing_report_routes_keep_their_methods(schema: dict[str, Any]) -> None:
    """배치 저장 경로가 더해져도 기존 저장 리포트 경로의 메서드는 그대로다.

    테스트 코드: RS-052
    """
    # when: 기존 경로의 메서드를 읽는다
    paths = schema["paths"]
    # then: 명세와 같다
    assert set(paths[BASE]) == {"get", "post"}
    assert set(paths[ID_ROUTE]) == {"get", "put", "delete"}
    assert set(paths[f"{ID_ROUTE}/copy"]) == {"post"}
    assert set(paths[f"{ID_ROUTE}/run"]) == {"post"}
