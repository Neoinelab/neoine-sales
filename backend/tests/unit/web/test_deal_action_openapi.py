"""Action API의 OpenAPI 계약(AC-17·21): 길이 제약 없음, 서버가 채우는 필드 없음, 전역 검색 없음.

커밋된 openapi.json과의 일치(드리프트)는 functional/platform이 검사한다. 이 파일은 새 계약의
핵심을 직접 고정해, 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

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
    name = _request_schema_names(schema, method, path)
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
    name = _request_schema_names(schema, method, path)
    request = schema["components"]["schemas"][name]

    assert not {"acted_at", "actor_user_id", "actor", "title", "content"} & set(
        request["properties"]
    )
    assert request["additionalProperties"] is False
    assert "action_type" in request["required"]
    assert not {"action", "next_action", "due_date"} & set(request["required"])


def test_only_the_create_request_accepts_a_status_change(schema: dict[str, Any]) -> None:
    create = _request_schema_names(schema, "post", "/api/v1/deals/{code}/actions")
    update = _request_schema_names(schema, "put", "/api/v1/deal-actions/{action_id}")

    assert "status_change" in schema["components"]["schemas"][create]["properties"]
    assert "status_change" not in schema["components"]["schemas"][update]["properties"]


def test_response_exposes_the_snapshot_and_nullable_plan_fields(schema: dict[str, Any]) -> None:
    response = schema["components"]["schemas"]["DealActionResponse"]
    props = response["properties"]

    assert {"status_key", "forecast_key", "acted_at", "actor", "deal_code", "updated_at"} <= set(
        props
    )
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
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    params = {p["name"]: p for p in operation["parameters"]}

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
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    body = schema["components"]["schemas"][str(ref).rsplit("/", 1)[-1]]

    assert set(body["properties"]) == {"items"}


def test_the_global_search_is_gone_but_the_single_action_routes_remain(
    schema: dict[str, Any],
) -> None:
    assert "/api/v1/deal-actions" not in schema["paths"]
    single = schema["paths"]["/api/v1/deal-actions/{action_id}"]
    assert set(single) == {"get", "put", "delete"}


def test_update_and_delete_document_the_403_and_404(schema: dict[str, Any]) -> None:
    single = schema["paths"]["/api/v1/deal-actions/{action_id}"]

    for method in ("put", "delete"):
        assert {"401", "403", "404"} <= set(single[method]["responses"]), method
    assert "204" in single["delete"]["responses"]
    assert {"401", "403", "404", "422"} <= set(single["put"]["responses"])


def test_there_is_no_action_type_enum_schema(schema: dict[str, Any]) -> None:
    assert "ActionType" not in schema["components"]["schemas"]


def test_the_search_filters_by_type_id_as_an_integer(schema: dict[str, Any]) -> None:
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    params = {p["name"]: p for p in operation["parameters"]}
    assert "action_type_id" in params
    param = params["action_type_id"]

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
    name = _request_schema_names(schema, method, path)
    props = schema["components"]["schemas"][name]["properties"]

    assert props["action_type"]["$ref"].endswith("/CatalogChoiceRequest")
    assert "action_type" in schema["components"]["schemas"][name]["required"]
    choice = schema["components"]["schemas"]["CatalogChoiceRequest"]
    assert set(choice["properties"]) == {"id", "name"}
    assert "required" not in choice or not choice["required"]


def test_the_response_type_is_an_id_and_name_object(schema: dict[str, Any]) -> None:
    props = schema["components"]["schemas"]["DealActionResponse"]["properties"]
    named = schema["components"]["schemas"][props["action_type"]["$ref"].rsplit("/", 1)[-1]]

    assert set(named["properties"]) == {"id", "name"}
    assert set(named["required"]) == {"id", "name"}
    assert "action_type" in schema["components"]["schemas"]["DealActionResponse"]["required"]


def test_the_create_request_documents_status_changes(schema: dict[str, Any]) -> None:
    create = _request_schema_names(schema, "post", "/api/v1/deals/{code}/actions")
    update = _request_schema_names(schema, "put", "/api/v1/deal-actions/{action_id}")
    props = schema["components"]["schemas"][create]["properties"]

    options = props["status_changes"]["anyOf"]
    array = next(o for o in options if o.get("type") == "array")
    assert array["maxItems"] == 2
    assert array["items"] == {"$ref": "#/components/schemas/ActionStatusChangeRequest"}
    assert _is_nullable(props["status_changes"])
    assert "status_change" in props
    assert "status_changes" not in schema["components"]["schemas"][update]["properties"]


@pytest.mark.parametrize("name", ["status_changes", "status_change"])
def test_the_create_request_describes_order_and_conflict_handling(
    schema: dict[str, Any], name: str
) -> None:
    create = _request_schema_names(schema, "post", "/api/v1/deals/{code}/actions")

    description = schema["components"]["schemas"][create]["properties"][name].get("description", "")

    assert "순서" in description
    assert "422" in description


def test_search_documents_the_next_action_status_filter(schema: dict[str, Any]) -> None:
    operation = schema["paths"]["/api/v1/deals/{code}/actions"]["get"]
    params = {p["name"]: p for p in operation["parameters"]}

    assert params["next_action_status"]["required"] is False
    filter_schema = schema["components"]["schemas"]["NextActionStatusFilter"]
    assert filter_schema["enum"] == ["open", "done", "not_done", "closed"]


def test_status_route_documents_request_response_and_errors(schema: dict[str, Any]) -> None:
    path = "/api/v1/deal-actions/{action_id}/next-action-status"
    operation = schema["paths"][path]["put"]

    name = _request_schema_names(schema, "put", path)
    request = schema["components"]["schemas"][name]
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
