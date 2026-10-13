"""활동 API의 OpenAPI 계약(AC15): 필드 개명·필수/nullable·검색 파라미터·Deal 삭제의 409 문서화.

커밋된 openapi.json과의 일치(드리프트)는 test_openapi_contract.py가 검사한다. 이 파일은 새 계약의
핵심을 직접 고정해, openapi.json이 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.fakes.use_cases import FakeUseCases


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()


def _is_nullable(prop: dict[str, Any]) -> bool:
    return any(option.get("type") == "null" for option in prop.get("anyOf", []))


def test_request_has_the_new_fields_and_requires_the_plan_fields(schema: dict[str, Any]) -> None:
    request = schema["components"]["schemas"]["DealActionRequest"]

    assert {"action", "next_action", "due_date", "memo"} <= set(request["properties"])
    assert not {"title", "content"} & set(request["properties"])
    assert {"action", "next_action", "due_date"} <= set(request["required"])
    assert "memo" not in request["required"]
    assert request["properties"]["due_date"]["format"] == "date"
    assert request["additionalProperties"] is False


def test_response_exposes_nullable_plan_fields_and_no_legacy_fields(schema: dict[str, Any]) -> None:
    response = schema["components"]["schemas"]["DealActionResponse"]
    props = response["properties"]

    assert {"action", "next_action", "due_date", "memo", "updated_at"} <= set(props)
    assert not {"title", "content"} & set(props)
    assert _is_nullable(props["next_action"])
    assert _is_nullable(props["due_date"])
    assert {"action", "memo"} <= set(response["required"])


@pytest.mark.parametrize("path", ["/api/v1/deal-actions", "/api/v1/deals/{deal_id}/actions"])
def test_search_documents_due_range_and_sort_parameters(schema: dict[str, Any], path: str) -> None:
    params = {p["name"]: p for p in schema["paths"][path]["get"]["parameters"]}

    assert {"due_from", "due_to", "sort"} <= set(params)
    assert params["sort"]["required"] is False
    sort_schema = schema["components"]["schemas"]["DealActionSort"]
    assert set(sort_schema["enum"]) == {"acted_at_desc", "due_date_asc", "due_date_desc"}
    assert sort_schema["enum"][0] == "acted_at_desc"


def test_delete_deal_documents_the_409_in_use_response(schema: dict[str, Any]) -> None:
    responses = schema["paths"]["/api/v1/deals/{deal_id}"]["delete"]["responses"]

    assert "409" in responses
    assert "204" in responses
