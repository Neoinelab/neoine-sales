"""저장 리포트 차트 OpenAPI 계약: 요청 chart, 응답 chart·chart_problem·chart_kind(RC-R23).

스키마 이름은 구현이 정하므로 `$ref`를 따라가서 필드 구성만 본다. 기존 필드·경로는 그대로다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BASE = "/api/v1/reports"
ID_ROUTE = f"{BASE}/{{report_id}}"
KINDS = {
    # 옛 10종
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
    # 새 23종
    "stacked_horizontal_bar",
    "stacked_100_horizontal_bar",
    "line_markers",
    "stacked_line",
    "stacked_line_markers",
    "stacked_100_line",
    "stacked_100_line_markers",
    "stacked_area",
    "stacked_100_area",
    "scatter_smooth_markers",
    "scatter_smooth",
    "scatter_line_markers",
    "scatter_line",
    "bubble",
    "radar",
    "radar_markers",
    "radar_filled",
    "treemap",
    "sunburst",
    "histogram",
    "pareto",
    "waterfall",
    "funnel",
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
    "histogram",
    "show_total",
    "combo_series",
}
BIN_KEYS = {"bin_mode", "bin_count", "bin_width", "overflow", "underflow"}


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
    """요청의 chart는 POST·PUT 모두 선택·nullable 필드다.

    테스트 코드: RC-046
    """
    # when: POST·PUT 요청 스키마를 읽는다
    body = _request(schema, method)

    # then: chart 속성이 있고 필수가 아니며 null을 받는다
    assert "chart" in body["properties"]
    assert "chart" not in body["required"]
    assert _is_nullable(body["properties"]["chart"])


@pytest.mark.parametrize("method", ["post", "put"])
def test_request_chart_has_the_sixteen_keys_and_forbids_unknown_ones(
    schema: dict[str, Any], method: str
) -> None:
    """요청 차트는 16키를 가지고 알 수 없는 키를 금지한다.

    테스트 코드: RC-046
    """
    # when: 요청 차트 스키마를 읽는다
    chart = _non_null(schema, _request(schema, method)["properties"]["chart"])

    # then: 16키이고 필수는 kind·category·values이며 추가 키는 금지다
    assert len(KINDS) == 33
    assert len(CHART_KEYS) == 16
    assert set(chart["properties"]) == CHART_KEYS
    assert set(chart["required"]) == {"kind", "category", "values"}
    assert chart.get("additionalProperties") is False


def test_copy_request_has_no_chart(schema: dict[str, Any]) -> None:
    """복제 요청 스키마에는 chart가 없다.

    테스트 코드: RC-046
    """
    # when: 복제 요청 스키마를 읽는다
    body = schema["paths"][f"{ID_ROUTE}/copy"]["post"]["requestBody"]["content"]
    copy = _resolve(schema, body["application/json"]["schema"])

    # then: chart 속성이 없다
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
    """상세 응답(POST·GET·PUT·복제)은 타입이 있는 chart와 chart_problem을 가진다.

    테스트 코드: RC-046
    """
    # when: 상세 응답 스키마를 읽는다
    properties = _response(schema, method, path, code)["properties"]

    # then: chart는 nullable이고 16키 모두 필수이며 kind는 33값 enum, chart_problem은 nullable
    #   문자열이다
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
    """목록 항목은 chart_kind만 가지고 chart·chart_problem은 없다.

    테스트 코드: RC-046
    """
    # when: 목록 응답 스키마를 읽는다
    listing = _response(schema, "get", BASE, "200")
    item = _resolve(schema, listing["items"])

    # then: chart_kind는 nullable 33값 enum이고 chart·chart_problem은 없다
    assert "chart_kind" in item["properties"]
    assert "chart" not in item["properties"]
    assert "chart_problem" not in item["properties"]
    assert _is_nullable(item["properties"]["chart_kind"])
    assert _kind_values(schema, item["properties"]["chart_kind"]) == KINDS


def test_run_and_query_contracts_are_unchanged_by_the_chart(schema: dict[str, Any]) -> None:
    """실행·조회 계약은 차트와 무관하다.

    테스트 코드: RC-046
    """
    # when: 실행 응답, 조회 응답, 조회 요청 스키마를 읽는다
    run = _response(schema, "post", f"{ID_ROUTE}/run", "200")
    query = _response(schema, "post", f"{BASE}/query", "200")
    query_request = _resolve(
        schema,
        schema["paths"][f"{BASE}/query"]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ],
    )

    # then: 실행 응답과 조회 응답이 같고 chart 속성이 없다
    assert run == query
    assert "chart" not in query_request["properties"]
    assert "chart" not in run["properties"]


def _detail_chart(schema: dict[str, Any]) -> dict[str, Any]:
    properties = _response(schema, "get", ID_ROUTE, "200")["properties"]
    return _non_null(schema, properties["chart"])


def test_response_category_is_nullable(schema: dict[str, Any]) -> None:
    """응답 차트의 범주는 nullable 정수다.

    테스트 코드: RC-046
    """
    # when: 상세 응답 차트 스키마를 읽는다
    chart = _detail_chart(schema)

    # then: category가 null 또는 정수다
    assert _is_nullable(chart["properties"]["category"])
    assert _non_null(schema, chart["properties"]["category"])["type"] == "integer"


def test_request_category_is_nullable_for_the_histogram(schema: dict[str, Any]) -> None:
    """요청 차트의 범주는 필수 키지만 null을 받고 새 옵션 키는 필수가 아니다.

    테스트 코드: RC-046
    """
    # when: 요청 차트 스키마를 읽는다
    chart = _non_null(schema, _request(schema, "post")["properties"]["chart"])

    # then: category는 필수이고 histogram·show_total·combo_series는 필수가 아니다
    assert "category" in chart["required"]
    assert chart["properties"]["category"].get("type") in {None, "integer"}
    assert "histogram" not in chart["required"]
    assert "show_total" not in chart["required"]
    assert "combo_series" not in chart["required"]


def test_histogram_response_schema_has_five_bin_keys(schema: dict[str, Any]) -> None:
    """응답의 구간 설정 스키마는 5키이고 방식은 3값 enum이다.

    테스트 코드: RC-046
    """
    # when: 상세 응답 차트의 histogram 스키마를 읽는다
    chart = _detail_chart(schema)
    histogram = chart["properties"]["histogram"]

    # then: nullable이고 5키 모두 필수이며 bin_mode는 auto·count·width, 나머지 칸은 nullable이다
    assert _is_nullable(histogram)
    bins = _non_null(schema, histogram)
    assert set(bins["properties"]) == BIN_KEYS
    assert set(bins["required"]) == BIN_KEYS
    assert set(_non_null(schema, bins["properties"]["bin_mode"])["enum"]) == {
        "auto",
        "count",
        "width",
    }
    for key in ("bin_count", "bin_width", "overflow", "underflow"):
        assert _is_nullable(bins["properties"][key])


def test_combo_series_response_schema_has_type_and_secondary(schema: dict[str, Any]) -> None:
    """응답의 콤보 계열 스키마는 type(6값 enum)과 secondary 두 키다.

    테스트 코드: RC-046
    """
    # when: 상세 응답 차트의 combo_series 스키마를 읽는다
    chart = _detail_chart(schema)
    combo = chart["properties"]["combo_series"]

    # then: nullable 목록이고 항목은 type·secondary 두 키가 모두 필수이며 type은 6종 enum이다
    assert _is_nullable(combo)
    array = next(n for n in combo["anyOf"] if n.get("type") == "array")
    item = _resolve(schema, array["items"])
    assert set(item["properties"]) == {"type", "secondary"}
    assert set(item["required"]) == {"type", "secondary"}
    assert set(_non_null(schema, item["properties"]["type"])["enum"]) == {
        "column",
        "stacked_column",
        "line",
        "line_markers",
        "area",
        "stacked_area",
    }
    assert item["properties"]["secondary"]["type"] == "boolean"


def test_show_total_response_is_a_required_boolean(schema: dict[str, Any]) -> None:
    """응답의 show_total은 필수 bool이다.

    테스트 코드: RC-046
    """
    # when: 상세 응답 차트 스키마를 읽는다
    chart = _detail_chart(schema)

    # then: show_total이 boolean이고 필수다
    assert chart["properties"]["show_total"]["type"] == "boolean"
    assert "show_total" in chart["required"]
