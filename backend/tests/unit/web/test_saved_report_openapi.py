"""저장 리포트 API의 OpenAPI 계약: 경로·메서드, 응답 코드, 요청·응답 필드.

스키마 이름은 구현이 정하므로 `$ref`를 따라가서 필드 구성만 본다.
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
DETAIL_ONLY = {"revision", "definition", "generated_sql", "chart", "chart_problem", "layout"}
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
    "chart_kind",
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
    """저장 리포트 경로 4개의 메서드가 명세와 같다(11개 메서드 중 배치 저장 제외).

    테스트 코드: RS-052
    """
    # when: 저장 리포트 경로의 메서드를 읽는다
    paths = schema["paths"]
    # then: 목록·만들기, 상세·덮어쓰기·삭제, 복제, 실행이다
    assert set(paths[BASE]) == {"get", "post"}
    assert set(paths[ID_ROUTE]) == {"get", "put", "delete"}
    assert set(paths[f"{ID_ROUTE}/copy"]) == {"post"}
    assert set(paths[f"{ID_ROUTE}/run"]) == {"post"}


def test_the_existing_reports_routes_keep_their_contract(schema: dict[str, Any]) -> None:
    """기존 필드 목록·조회 경로의 메서드와 응답 코드는 저장 기능을 더해도 그대로다."""
    # when: 필드 목록·조회 경로의 메서드와 응답 코드를 읽는다
    paths = schema["paths"]
    fields_methods = set(paths[f"{BASE}/fields"])
    query_methods = set(paths[f"{BASE}/query"])
    query_codes = set(paths[f"{BASE}/query"]["post"]["responses"])
    fields_codes = set(paths[f"{BASE}/fields"]["get"]["responses"])
    # then: 필드 목록은 get 하나(422 없음), 조회는 post 하나(200·401·422·503)다
    assert fields_methods == {"get"}
    assert query_methods == {"post"}
    assert {"200", "401", "422", "503"} <= query_codes
    assert "422" not in fields_codes


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
    """각 경로의 성공 코드와 401이 문서화되어 있다.

    테스트 코드: RS-052
    """
    # when: 경로의 응답 코드를 읽는다
    responses = schema["paths"][path][method]["responses"]
    # then: 성공 코드와 401이 있다
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
    """각 경로의 오류 코드가 명세대로 문서화되어 있다.

    테스트 코드: RS-052
    """
    # when: 경로의 응답 코드를 읽는다
    documented = set(schema["paths"][path][method]["responses"])
    # then: 명세의 오류 코드가 모두 있다
    assert codes <= documented


def test_the_list_route_documents_no_path_errors(schema: dict[str, Any]) -> None:
    """목록 경로에는 404·403이 문서화되지 않는다(로그인한 모든 역할이 쓴다).

    테스트 코드: RS-052
    """
    # when: 목록 경로의 응답 코드를 읽는다
    responses = schema["paths"][BASE]["get"]["responses"]
    # then: 404·403이 없다
    assert "404" not in responses
    assert "403" not in responses


def test_report_id_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    """리포트 id 경로 파라미터는 1~2^53-1 범위의 정수다.

    테스트 코드: RS-052
    """
    # when: 상세·덮어쓰기·삭제의 report_id 파라미터 스키마를 읽는다
    params = {
        method: [
            p for p in schema["paths"][ID_ROUTE][method]["parameters"] if p["name"] == "report_id"
        ]
        for method in ("get", "put", "delete")
    }
    # then: 정수이고 범위가 1~MAX_ID다
    for found in params.values():
        (param,) = found
        assert param["schema"]["type"] == "integer"
        assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)


def test_request_bodies_have_the_planned_fields_and_no_sql(schema: dict[str, Any]) -> None:
    """만들기·덮어쓰기·복제 요청 필드가 명세와 같고 SQL 필드가 없다.

    테스트 코드: RS-052
    """
    # when: 세 요청 스키마를 읽는다
    create = _body_schema(schema, "post", BASE)
    update = _body_schema(schema, "put", ID_ROUTE)
    copy = _body_schema(schema, "post", f"{ID_ROUTE}/copy")
    # then: 필드 구성이 명세와 같고 generated_sql이 없다
    assert set(create["properties"]) == {
        "name",
        "description",
        "visibility",
        "definition",
        "chart",
        "layout",
    }
    assert set(update["properties"]) == {
        "name",
        "description",
        "visibility",
        "definition",
        "chart",
        "layout",
        "revision",
    }
    assert set(copy["properties"]) == {"name", "description", "visibility"}
    assert "generated_sql" not in create["properties"]


def test_required_request_fields(schema: dict[str, Any]) -> None:
    """요청의 필수 필드가 명세와 같다(설명·차트·배치는 선택).

    테스트 코드: RS-052
    """
    # when: 세 요청 스키마를 읽는다
    create = _body_schema(schema, "post", BASE)
    update = _body_schema(schema, "put", ID_ROUTE)
    copy = _body_schema(schema, "post", f"{ID_ROUTE}/copy")
    # then: 필수 필드가 명세와 같다
    assert set(create["required"]) == {"name", "visibility", "definition"}
    assert set(update["required"]) == {"name", "visibility", "definition", "revision"}
    assert set(copy["required"]) == {"name", "visibility"}


def test_update_revision_is_an_integer_of_at_least_one(schema: dict[str, Any]) -> None:
    """덮어쓰기 요청의 revision은 정수이고 최소 1이다.

    테스트 코드: RS-052
    """
    # when: revision 필드 스키마를 읽는다
    revision = _body_schema(schema, "put", ID_ROUTE)["properties"]["revision"]
    # then: 정수, 최소 1이다
    assert revision["type"] == "integer"
    assert revision["minimum"] == 1


def test_detail_responses_carry_revision_definition_and_sql(schema: dict[str, Any]) -> None:
    """상세 응답 4종은 목록 항목 필드에 revision·정의·SQL·차트·배치가 더해져 있다.

    테스트 코드: RS-052
    """
    # when: 만들기·상세·덮어쓰기·복제 응답 스키마의 필드를 읽는다
    fields = {
        (method, path): set(_response_schema(schema, method, path, code)["properties"])
        for method, path, code in [
            ("post", BASE, "201"),
            ("get", ID_ROUTE, "200"),
            ("put", ID_ROUTE, "200"),
            ("post", f"{ID_ROUTE}/copy", "201"),
        ]
    }
    # then: 모두 요약 필드 + 상세 필드다
    for key, properties in fields.items():
        assert properties == SUMMARY_FIELDS | DETAIL_ONLY, key


def test_list_items_are_summaries_without_the_definition(schema: dict[str, Any]) -> None:
    """목록 응답은 배열이고 항목에는 정의·배치가 없는 요약 필드뿐이다.

    테스트 코드: RS-052
    """
    # when: 목록 응답 스키마를 읽는다
    listing = _response_schema(schema, "get", BASE, "200")
    item = _resolve(schema, listing["items"])
    # then: 배열이고 항목 필드가 요약 필드다
    assert listing["type"] == "array"
    assert set(item["properties"]) == SUMMARY_FIELDS


def test_user_columns_use_the_shared_user_ref_schema(schema: dict[str, Any]) -> None:
    """만든 사람·최종 수정자는 공통 UserRef 스키마를 쓴다.

    테스트 코드: RS-052
    """
    # when: 목록 항목 스키마를 읽는다
    item = _resolve(schema, _response_schema(schema, "get", BASE, "200")["items"])
    # then: owner·updated_by가 UserRef를 가리킨다
    for field in ("owner", "updated_by"):
        assert item["properties"][field]["$ref"].endswith("/UserRef"), field


def test_run_response_is_the_query_response_schema(schema: dict[str, Any]) -> None:
    """실행 응답 스키마는 조회(/query) 응답 스키마와 같다.

    테스트 코드: RS-052
    """
    # when: 실행·조회 응답 스키마를 읽는다
    run = _response_schema(schema, "post", f"{ID_ROUTE}/run", "200")
    query = _response_schema(schema, "post", f"{BASE}/query", "200")
    # then: 같다
    assert run == query
