"""저장 리포트 API의 OpenAPI 계약(AC20): 경로·메서드, 응답 코드, 요청·응답 필드.

스키마 이름은 구현이 정하므로 `$ref`를 따라가서 필드 구성만 본다.
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
DETAIL_ONLY = {"revision", "definition", "generated_sql"}
SUMMARY_FIELDS = {
    "id",
    "name",
    "description",
    "visibility",
    "owner",
    "updated_by",
    "entities",
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


def _body_schema(schema: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    body = schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    return _resolve(schema, body)


def _response_schema(schema: dict[str, Any], method: str, path: str, code: str) -> dict[str, Any]:
    content = schema["paths"][path][method]["responses"][code]["content"]["application/json"]
    return _resolve(schema, content["schema"])


def test_saved_report_paths_and_methods(schema: dict[str, Any]) -> None:
    paths = schema["paths"]

    assert set(paths[BASE]) == {"get", "post"}
    assert set(paths[ID_ROUTE]) == {"get", "put", "delete"}
    assert set(paths[f"{ID_ROUTE}/copy"]) == {"post"}
    assert set(paths[f"{ID_ROUTE}/run"]) == {"post"}


def test_the_existing_reports_routes_keep_their_contract(schema: dict[str, Any]) -> None:
    paths = schema["paths"]

    assert set(paths[f"{BASE}/fields"]) == {"get"}
    assert set(paths[f"{BASE}/query"]) == {"post"}
    assert {"200", "401", "422", "503"} <= set(paths[f"{BASE}/query"]["post"]["responses"])
    assert "422" not in paths[f"{BASE}/fields"]["get"]["responses"]


@pytest.mark.parametrize(
    ("method", "path", "success"),
    [
        ("get", BASE, "200"),
        ("post", BASE, "201"),
        ("get", ID_ROUTE, "200"),
        ("put", ID_ROUTE, "200"),
        ("delete", ID_ROUTE, "204"),
        ("post", f"{ID_ROUTE}/copy", "201"),
        ("post", f"{ID_ROUTE}/run", "200"),
    ],
)
def test_success_status_codes(schema: dict[str, Any], method: str, path: str, success: str) -> None:
    responses = schema["paths"][path][method]["responses"]

    assert success in responses
    assert "401" in responses


@pytest.mark.parametrize(
    ("method", "path", "codes"),
    [
        ("post", BASE, {"409", "422"}),
        ("get", ID_ROUTE, {"404", "422"}),
        ("put", ID_ROUTE, {"403", "404", "409", "422"}),
        ("delete", ID_ROUTE, {"403", "404", "422"}),
        ("post", f"{ID_ROUTE}/copy", {"404", "409", "422"}),
        ("post", f"{ID_ROUTE}/run", {"404", "422", "503"}),
    ],
)
def test_error_status_codes_are_documented(
    schema: dict[str, Any], method: str, path: str, codes: set[str]
) -> None:
    assert codes <= set(schema["paths"][path][method]["responses"])


def test_the_list_route_documents_no_path_errors(schema: dict[str, Any]) -> None:
    responses = schema["paths"][BASE]["get"]["responses"]

    assert "404" not in responses
    assert "403" not in responses  # 로그인한 모든 역할이 쓴다


def test_report_id_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    for method in ("get", "put", "delete"):
        (param,) = [
            p for p in schema["paths"][ID_ROUTE][method]["parameters"] if p["name"] == "report_id"
        ]
        assert param["schema"]["type"] == "integer"
        assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)


def test_request_bodies_have_the_planned_fields_and_no_sql(schema: dict[str, Any]) -> None:
    create = _body_schema(schema, "post", BASE)
    update = _body_schema(schema, "put", ID_ROUTE)
    copy = _body_schema(schema, "post", f"{ID_ROUTE}/copy")

    assert set(create["properties"]) == {"name", "description", "visibility", "definition"}
    assert set(update["properties"]) == {
        "name",
        "description",
        "visibility",
        "definition",
        "revision",
    }
    assert set(copy["properties"]) == {"name", "description", "visibility"}
    assert "generated_sql" not in create["properties"]


def test_required_request_fields(schema: dict[str, Any]) -> None:
    create = _body_schema(schema, "post", BASE)
    update = _body_schema(schema, "put", ID_ROUTE)
    copy = _body_schema(schema, "post", f"{ID_ROUTE}/copy")

    assert set(create["required"]) == {"name", "visibility", "definition"}
    assert set(update["required"]) == {"name", "visibility", "definition", "revision"}
    assert set(copy["required"]) == {"name", "visibility"}


def test_update_revision_is_an_integer_of_at_least_one(schema: dict[str, Any]) -> None:
    revision = _body_schema(schema, "put", ID_ROUTE)["properties"]["revision"]

    assert revision["type"] == "integer"
    assert revision["minimum"] == 1


def test_detail_responses_carry_revision_definition_and_sql(schema: dict[str, Any]) -> None:
    for method, path, code in [
        ("post", BASE, "201"),
        ("get", ID_ROUTE, "200"),
        ("put", ID_ROUTE, "200"),
        ("post", f"{ID_ROUTE}/copy", "201"),
    ]:
        properties = set(_response_schema(schema, method, path, code)["properties"])
        assert properties == SUMMARY_FIELDS | DETAIL_ONLY, (method, path)


def test_list_items_are_summaries_without_the_definition(schema: dict[str, Any]) -> None:
    listing = _response_schema(schema, "get", BASE, "200")
    item = _resolve(schema, listing["items"])

    assert listing["type"] == "array"
    assert set(item["properties"]) == SUMMARY_FIELDS


def test_user_columns_use_the_shared_user_ref_schema(schema: dict[str, Any]) -> None:
    item = _resolve(schema, _response_schema(schema, "get", BASE, "200")["items"])

    for field in ("owner", "updated_by"):
        assert item["properties"][field]["$ref"].endswith("/UserRef"), field


def test_run_response_is_the_query_response_schema(schema: dict[str, Any]) -> None:
    run = _response_schema(schema, "post", f"{ID_ROUTE}/run", "200")
    query = _response_schema(schema, "post", f"{BASE}/query", "200")

    assert run == query
