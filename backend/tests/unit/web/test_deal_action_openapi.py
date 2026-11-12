"""Action API의 OpenAPI 계약: 길이 제약 없음, 서버가 채우는 필드 없음, 전역 검색 없음.

커밋된 openapi.json과의 일치(드리프트)는
PL-034(`test_openapi_contract.py`)가 검사한다. 이 파일은 새 계약의
핵심을 직접 고정해, 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
TEXT_FIELDS = ("action", "next_action", "memo")


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _is_nullable(prop: dict[str, Any]) -> bool:
    return any(option.get("type") == "null" for option in prop.get("anyOf", []))


def _request_schema_names(schema: dict[str, Any], method: str, path: str) -> str:
    body = schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    return str(body["$ref"]).rsplit("/", 1)[-1]


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/api/v1/deals/{code}/actions"), ("put", "/api/v1/deal-actions/{action_id}")],
)
def test_action_request_schemas_have_no_max_length(
    schema: dict[str, Any], method: str, path: str
) -> None:
    """등록·수정 요청의 텍스트 칸에는 길이 상한이 없다.

    테스트 코드: AC-070
    """
    # when: 요청 스키마를 찾는다
    name = _request_schema_names(schema, method, path)
    # then: 진행사항·Next Action·Memo에 maxLength가 없다
    props = schema["components"]["schemas"][name]["properties"]

    for field in TEXT_FIELDS:
        assert "maxLength" not in props[field], (name, field)
        assert props[field]["type"] == "string"


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/api/v1/deals/{code}/actions"), ("put", "/api/v1/deal-actions/{action_id}")],
)
def test_action_requests_do_not_take_server_filled_fields(
    schema: dict[str, Any], method: str, path: str
) -> None:
    """등록·수정 요청에는 서버가 채우는 필드가 없고 유형만 필수다.

    테스트 코드: AC-070
    """
    # when: 요청 스키마를 찾는다
    name = _request_schema_names(schema, method, path)
    request = schema["components"]["schemas"][name]

    # then: 서버 필드가 없고 추가 필드는 거부하며 유형만 필수다
    assert not {"acted_at", "actor_user_id", "actor", "title", "content"} & set(
        request["properties"]
    )
    assert request["additionalProperties"] is False
    assert "action_type" in request["required"]
    assert not {"action", "next_action", "due_date"} & set(request["required"])


def test_only_the_create_request_accepts_a_status_change(schema: dict[str, Any]) -> None:
    """동반 변경은 등록 요청에만 있다.

    테스트 코드: AC-070
    """
    # when: 등록·수정 요청 스키마를 찾는다
    create = _request_schema_names(schema, "post", "/api/v1/deals/{code}/actions")
    update = _request_schema_names(schema, "put", "/api/v1/deal-actions/{action_id}")

    # then: 등록에는 status_change가 있고 수정에는 없다
    assert "status_change" in schema["components"]["schemas"][create]["properties"]
    assert "status_change" not in schema["components"]["schemas"][update]["properties"]


def test_response_exposes_the_snapshot_and_nullable_plan_fields(schema: dict[str, Any]) -> None:
    """응답은 스냅숏과 null 허용 다섯 필드를 필수로 문서화한다.

    테스트 코드: AC-070
    """
    # when: 응답 스키마를 읽는다
    response = schema["components"]["schemas"]["DealActionResponse"]
    props = response["properties"]

    # then: 스냅숏·수행 정보가 있고 서버 내부 필드는 없다
    assert {"status_key", "forecast_key", "acted_at", "actor", "deal_code", "updated_at"} <= set(
        props
    )
    # then: null 허용 다섯 필드는 null을 허용하고 required에 있다
    for name in (
        "action",
        "next_action",
        "due_date",
        "next_action_status",
        "next_action_closed_at",
    ):
        assert _is_nullable(props[name]), name
    assert {
        "action",
        "next_action",
        "due_date",
        "next_action_status",
        "next_action_closed_at",
        "memo",
        "status_key",
        "forecast_key",
    } <= set(response["required"])
    assert "actor_user_id" not in props


def test_search_documents_the_date_filters_and_the_sorts_without_paging(
    schema: dict[str, Any],
) -> None:
    """Action 검색은 조건·정렬 파라미터를 문서화하고 페이지·구 파라미터는 없다.

    테스트 코드: NA-036, NA-043
    """
    # when: 목록 조회 operation의 파라미터와 정렬 스키마를 읽는다
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    params = {p["name"]: p for p in operation["parameters"]}
    # then: 조건·정렬은 있고 offset·limit·deal_code·action_type은 없으며 정렬 값은 10개다
    assert {
        "action_type_id",
        "actor_user_id",
        "keyword",
        "acted_from",
        "acted_to",
        "due_from",
        "due_to",
        "sort",
    } <= set(params)
    assert not {"offset", "limit", "deal_code", "action_type"} & set(params)
    assert params["sort"]["required"] is False
    sort_schema = schema["components"]["schemas"]["DealActionSort"]
    assert sort_schema["enum"] == [
        "acted_at_desc",
        "acted_at_asc",
        "due_date_asc",
        "due_date_desc",
        "actor_asc",
        "actor_desc",
        "action_type_asc",
        "action_type_desc",
        "next_action_status_asc",
        "next_action_status_desc",
    ]


def test_the_list_response_is_an_items_object_without_a_page(schema: dict[str, Any]) -> None:
    """목록 응답은 `items` 키 하나뿐이고 페이지 필드가 없다.

    테스트 코드: NA-019
    """
    # when: 목록 응답 스키마를 읽는다
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    body = schema["components"]["schemas"][str(ref).rsplit("/", 1)[-1]]
    # then: 속성은 items 하나다
    assert set(body["properties"]) == {"items"}


def test_the_global_search_is_gone_but_the_single_action_routes_remain(
    schema: dict[str, Any],
) -> None:
    """전역 Action 검색 경로는 없고 개별 Action 경로와 상태 변경 경로만 있다.

    테스트 코드: NA-022
    """
    # when: API 문서의 경로 목록을 본다
    paths = schema["paths"]
    # then: 전역 검색은 없고 개별 경로(GET·PUT·DELETE)와 next-action-status(PUT)는 있다
    assert "/api/v1/deal-actions" not in paths
    assert set(paths["/api/v1/deal-actions/{action_id}"]) == {"get", "put", "delete"}
    assert set(paths["/api/v1/deal-actions/{action_id}/next-action-status"]) == {"put"}


def test_update_and_delete_document_the_403_and_404(schema: dict[str, Any]) -> None:
    """수정·삭제는 401·403·404를 문서화한다.

    테스트 코드: AC-070
    """
    # when: 수정·삭제 operation을 읽는다
    single = schema["paths"]["/api/v1/deal-actions/{action_id}"]

    # then: 두 operation에 401·403·404가 있고 삭제는 204, 수정은 422도 있다
    for method in ("put", "delete"):
        assert {"401", "403", "404"} <= set(single[method]["responses"]), method
    assert "204" in single["delete"]["responses"]
    assert {"401", "403", "404", "422"} <= set(single["put"]["responses"])


def test_there_is_no_action_type_enum_schema(schema: dict[str, Any]) -> None:
    """유형 enum 스키마는 없다.

    테스트 코드: AC-070
    """
    # when·then: 스키마 목록에 ActionType이 없다
    assert "ActionType" not in schema["components"]["schemas"]


def test_the_search_filters_by_type_id_as_an_integer(schema: dict[str, Any]) -> None:
    """Action 검색의 action_type_id 파라미터는 선택 정수이고 uuid가 아니다."""
    # when: 검색 연산의 파라미터를 읽는다
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    params = {p["name"]: p for p in operation["parameters"]}
    assert "action_type_id" in params
    param = params["action_type_id"]

    # then: 필수가 아니고 정수형이며 uuid 형식은 아니다
    assert param["required"] is False
    assert any(option.get("type") == "integer" for option in param["schema"]["anyOf"])
    assert not any(option.get("format") == "uuid" for option in param["schema"]["anyOf"])


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/api/v1/deals/{code}/actions"), ("put", "/api/v1/deal-actions/{action_id}")],
)
def test_the_request_takes_a_choice_object_for_the_type(
    schema: dict[str, Any], method: str, path: str
) -> None:
    """요청은 유형을 선택 객체로 받는다.

    테스트 코드: AC-070
    """
    # when: 요청 스키마를 찾는다
    name = _request_schema_names(schema, method, path)
    props = schema["components"]["schemas"][name]["properties"]

    # then: 유형은 필수 CatalogChoiceRequest이고 id·이름이 선택이다
    assert props["action_type"]["$ref"].endswith("/CatalogChoiceRequest")
    assert "action_type" in schema["components"]["schemas"][name]["required"]
    choice = schema["components"]["schemas"]["CatalogChoiceRequest"]
    assert set(choice["properties"]) == {"id", "name"}
    assert "required" not in choice or not choice["required"]


def test_the_response_type_is_an_id_and_name_object(schema: dict[str, Any]) -> None:
    """응답의 유형은 id와 이름 객체다.

    테스트 코드: AC-070
    """
    # when: 응답 스키마를 읽는다
    props = schema["components"]["schemas"]["DealActionResponse"]["properties"]
    named = schema["components"]["schemas"][props["action_type"]["$ref"].rsplit("/", 1)[-1]]

    # then: 유형은 필수 {id, name}이다
    assert set(named["properties"]) == {"id", "name"}
    assert set(named["required"]) == {"id", "name"}
    assert "action_type" in schema["components"]["schemas"]["DealActionResponse"]["required"]


def test_the_create_request_documents_status_changes(schema: dict[str, Any]) -> None:
    """등록 요청은 최대 2건의 status_changes를 문서화한다.

    테스트 코드: AC-070
    """
    # when: 등록·수정 요청 스키마를 찾는다
    create = _request_schema_names(schema, "post", "/api/v1/deals/{code}/actions")
    update = _request_schema_names(schema, "put", "/api/v1/deal-actions/{action_id}")
    props = schema["components"]["schemas"][create]["properties"]

    # then: status_changes는 최대 2건 배열이고 null을 허용한다
    options = props["status_changes"]["anyOf"]
    array = next(o for o in options if o.get("type") == "array")
    assert array["maxItems"] == 2
    assert array["items"] == {"$ref": "#/components/schemas/ActionStatusChangeRequest"}
    assert _is_nullable(props["status_changes"])
    # then: 등록에만 있고 수정에는 없다
    assert "status_change" in props
    assert "status_changes" not in schema["components"]["schemas"][update]["properties"]


@pytest.mark.parametrize("name", ["status_changes", "status_change"])
def test_the_create_request_describes_order_and_conflict_handling(
    schema: dict[str, Any], name: str
) -> None:
    """동반 변경 칸의 설명에 순서와 422가 쓰여 있다.

    테스트 코드: AC-070
    """
    # given: 등록 요청 스키마
    create = _request_schema_names(schema, "post", "/api/v1/deals/{code}/actions")

    # when: 칸 설명을 읽는다
    description = schema["components"]["schemas"][create]["properties"][name].get("description", "")

    # then: 설명에 "순서"와 "422"가 있다
    assert "순서" in description
    assert "422" in description


def test_search_documents_the_next_action_status_filter(schema: dict[str, Any]) -> None:
    """검색 문서에 선택 파라미터 next_action_status와 4값 필터 스키마가 있다.

    테스트 코드: NA-035
    """
    # when: 목록 조회 operation의 파라미터를 읽는다
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    params = {p["name"]: p for p in operation["parameters"]}
    # then: 선택 파라미터이고 필터 스키마는 open·done·not_done·closed다
    assert params["next_action_status"]["required"] is False
    filter_schema = schema["components"]["schemas"]["NextActionStatusFilter"]
    assert filter_schema["enum"] == ["open", "done", "not_done", "closed"]


def test_status_route_documents_request_response_and_errors(schema: dict[str, Any]) -> None:
    """상태 변경 경로는 요청·응답과 401/403/404/409/422를 문서화한다."""
    # when: 상태 변경 operation을 읽는다
    path = "/api/v1/deal-actions/{action_id}/next-action-status"
    operation = schema["paths"][path]["put"]
    name = _request_schema_names(schema, "put", path)
    request = schema["components"]["schemas"][name]
    # then: 본문은 status(필수)·memo이고 모르는 필드를 거절하며 응답과 오류 코드가 문서에 있다
    assert set(request["properties"]) == {"status", "memo"}
    assert request["required"] == ["status"]
    assert request["additionalProperties"] is False
    assert schema["components"]["schemas"]["NextActionStatus"]["enum"] == [
        "open",
        "done",
        "not_done",
    ]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert str(ref).endswith("/DealActionResponse")
    assert {"401", "403", "404", "409", "422"} <= set(operation["responses"])


def test_the_action_list_has_no_global_search_path_page_or_paging_parameters(
    schema: dict[str, Any],
) -> None:
    """Deal의 Action 목록은 `items` 하나뿐이고 전역 목록 경로와 페이지 파라미터가 없다.

    테스트 코드: AC-070
    """
    # when: 목록 operation과 경로 목록을 읽는다
    paths = schema["paths"]
    operation = paths["/api/v1/deals/{code}/actions"]["get"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    body = schema["components"]["schemas"][str(ref).rsplit("/", 1)[-1]]
    params = {p["name"] for p in operation["parameters"]}
    # then: 전역 목록 경로는 없고 응답은 items 하나이며 offset·limit이 없다
    assert "/api/v1/deal-actions" not in paths
    assert set(body["properties"]) == {"items"}
    assert not {"offset", "limit"} & params


def test_the_action_type_routes_are_documented_with_their_responses(
    schema: dict[str, Any],
) -> None:
    """/api/v1/action-types의 4개 엔드포인트와 오류 응답이 OpenAPI에 문서화되어 있다."""
    # when: OpenAPI의 action-types 경로를 읽는다
    paths = schema["paths"]
    collection = paths["/api/v1/action-types"]
    item = paths["/api/v1/action-types/{type_id}"]
    # then: 목록·등록 / 이름 변경·삭제 메서드가 있다
    assert set(collection) == {"get", "post"}
    assert set(item) == {"patch", "delete"}
    # then: 등록은 201과 401·403·409·422를 문서화한다
    assert "201" in collection["post"]["responses"]
    assert {"401", "403", "409", "422"} <= set(collection["post"]["responses"])
    # then: 이름 변경은 401·403·404·409·422를 문서화한다
    assert {"401", "403", "404", "409", "422"} <= set(item["patch"]["responses"])
    # then: 삭제는 204와 401·403·404·409를 문서화한다
    assert {"204", "401", "403", "404", "409"} <= set(item["delete"]["responses"])
