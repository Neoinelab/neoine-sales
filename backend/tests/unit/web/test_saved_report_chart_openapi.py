"""저장 리포트 차트 OpenAPI 계약 (Reports 4단계 AC3·9): 요청 chart, 응답 chart·chart_kind.

스키마 이름은 구현이 정하므로 `$ref`를 따라가서 필드 구성만 본다. 기존 필드·경로는 그대로다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BASE = "/api/v1/reports"
ID_ROUTE = f"{BASE}/{{report_id}}"
KINDS = {
    "bar",
    "horizontal_bar",
    "stacked_bar",
    "stacked_100_bar",
    "line",
    "area",
    "pie",
    "doughnut",
    "scatter",
    "combo",
}
CHART_KEYS = {
    "kind",
    "category",
    "series",
    "values",
    "swap",
    "title",
    "legend",
    "data_labels",
    "category_axis_title",
    "value_axis_title",
    "value_min",
    "value_max",
    "secondary_axis",
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["components"]["schemas"][node["$ref"].rsplit("/", 1)[1]]
    return node


def _non_null(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """`X | None`(anyOf)에서 null이 아닌 쪽을 풀어 돌려준다."""
    if "anyOf" in node:
        (inner,) = [n for n in node["anyOf"] if n.get("type") != "null"]
        return _resolve(schema, inner)
    return _resolve(schema, node)


def _is_nullable(node: dict[str, Any]) -> bool:
    return any(n.get("type") == "null" for n in node.get("anyOf", []))


def _request(schema: dict[str, Any], method: str) -> dict[str, Any]:
    path = BASE if method == "post" else ID_ROUTE
    body = schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    return _resolve(schema, body)


def _response(schema: dict[str, Any], method: str, path: str, code: str) -> dict[str, Any]:
    content = schema["paths"][path][method]["responses"][code]["content"]["application/json"]
    return _resolve(schema, content["schema"])


def _kind_values(schema: dict[str, Any], node: dict[str, Any]) -> set[str]:
    resolved = _non_null(schema, node)
    return set(resolved["enum"])


@pytest.mark.parametrize("method", ["post", "put"])
def test_chart_is_an_optional_nullable_request_field(schema: dict[str, Any], method: str) -> None:
    body = _request(schema, method)

    assert "chart" in body["properties"]
    assert "chart" not in body["required"]
    assert _is_nullable(body["properties"]["chart"])


@pytest.mark.parametrize("method", ["post", "put"])
def test_request_chart_has_the_thirteen_keys_and_forbids_unknown_ones(
    schema: dict[str, Any], method: str
) -> None:
    chart = _non_null(schema, _request(schema, method)["properties"]["chart"])

    assert set(chart["properties"]) == CHART_KEYS
    assert set(chart["required"]) == {"kind", "category", "values"}
    assert chart.get("additionalProperties") is False


def test_copy_request_has_no_chart(schema: dict[str, Any]) -> None:
    body = schema["paths"][f"{ID_ROUTE}/copy"]["post"]["requestBody"]["content"]
    copy = _resolve(schema, body["application/json"]["schema"])

    assert "chart" not in copy["properties"]


@pytest.mark.parametrize(
    ("method", "path", "code"),
    [
        ("post", BASE, "201"),
        ("get", ID_ROUTE, "200"),
        ("put", ID_ROUTE, "200"),
        ("post", f"{ID_ROUTE}/copy", "201"),
    ],
)
def test_detail_responses_carry_a_typed_chart_and_the_problem(
    schema: dict[str, Any], method: str, path: str, code: str
) -> None:
    properties = _response(schema, method, path, code)["properties"]

    assert _is_nullable(properties["chart"])
    chart = _non_null(schema, properties["chart"])
    assert set(chart["properties"]) == CHART_KEYS
    assert set(chart["required"]) == CHART_KEYS  # 저장된 정규화 값이라 키가 모두 있다
    assert _kind_values(schema, chart["properties"]["kind"]) == KINDS
    assert _kind_values(schema, chart["properties"]["legend"]) == {"top", "right", "bottom", "none"}
    assert chart["properties"]["values"]["type"] == "array"
    assert chart["properties"]["values"]["items"]["type"] == "integer"
    assert _is_nullable(properties["chart_problem"])
    assert _non_null(schema, properties["chart_problem"])["type"] == "string"


def test_list_items_carry_only_the_chart_kind(schema: dict[str, Any]) -> None:
    listing = _response(schema, "get", BASE, "200")
    item = _resolve(schema, listing["items"])

    assert "chart_kind" in item["properties"]
    assert "chart" not in item["properties"]
    assert "chart_problem" not in item["properties"]
    assert _is_nullable(item["properties"]["chart_kind"])
    assert _kind_values(schema, item["properties"]["chart_kind"]) == KINDS


def test_run_and_query_contracts_are_unchanged_by_the_chart(schema: dict[str, Any]) -> None:
    run = _response(schema, "post", f"{ID_ROUTE}/run", "200")
    query = _response(schema, "post", f"{BASE}/query", "200")
    query_request = _resolve(
        schema,
        schema["paths"][f"{BASE}/query"]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ],
    )

    assert run == query
    assert "chart" not in query_request["properties"]
    assert "chart" not in run["properties"]
