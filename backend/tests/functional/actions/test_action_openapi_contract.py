"""Feature: Action API의 공개 계약은 길이 제한이 없고, 목록은 {items}이며, 전역 검색이 없다.

실행 중인 앱의 /openapi.json을 읽어 확인한다. 커밋된 openapi.json과의 일치는
`platform/test_openapi_contract.py`가 본다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.platform import (
    operation_of,
    schema_name_of,
    spec_of,
    when_fetch_openapi,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

TEXT_FIELDS = ("action", "next_action", "memo")
CREATE = ("POST", "/api/v1/deals/{code}/actions")
UPDATE = ("PUT", "/api/v1/deal-actions/{action_id}")


async def test_action_request_bodies_have_no_length_limit_and_no_server_filled_fields(
    api: Api,
) -> None:
    """Scenario: 등록·수정 본문의 텍스트에는 maxLength가 없고 수행 일시·담당자 필드도 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    for method, path in (CREATE, UPDATE):
        name = schema_name_of(operation_of(spec, method, path), request=True)
        properties = spec["components"]["schemas"][name]["properties"]
        for field in TEXT_FIELDS:
            assert "maxLength" not in properties[field], (name, field)
        assert not {"acted_at", "actor_user_id", "actor"} & set(properties), name


async def test_action_search_is_per_deal_with_a_flat_items_response(api: Api) -> None:
    """Scenario: Action 검색은 Deal 아래에만 있고 응답은 페이지 정보 없는 {items}다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    assert "/api/v1/deal-actions" not in spec["paths"]
    operation = operation_of(spec, "GET", "/api/v1/deals/{code}/actions")
    names = {p["name"] for p in operation["parameters"]}
    assert not {"offset", "limit", "deal_code"} & names
    body = spec["components"]["schemas"][schema_name_of(operation, request=False)]
    assert set(body["properties"]) == {"items"}


async def test_action_type_is_a_choice_object_in_requests_and_id_name_in_responses(
    api: Api,
) -> None:
    """Scenario: 요청의 유형은 {id|name} 선택 객체, 응답은 {id, name}이고 enum 스키마는 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    schemas = spec["components"]["schemas"]
    assert "ActionType" not in schemas
    for method, path in (CREATE, UPDATE):
        name = schema_name_of(operation_of(spec, method, path), request=True)
        assert schemas[name]["properties"]["action_type"]["$ref"].endswith("/CatalogChoiceRequest")
        assert "action_type" in schemas[name]["required"]
    assert set(schemas["CatalogChoiceRequest"]["properties"]) == {"id", "name"}
    action_type = schemas["DealActionResponse"]["properties"]["action_type"]
    assert set(schemas[action_type["$ref"].rsplit("/", 1)[-1]]["properties"]) == {"id", "name"}


async def test_action_search_filters_by_type_id_not_by_the_old_enum(api: Api) -> None:
    """Scenario: Action 검색의 유형 조건은 action_type_id(UUID)이고 구 action_type은 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    operation = operation_of(spec_of(response), "GET", "/api/v1/deals/{code}/actions")
    names = {p["name"] for p in operation["parameters"]}
    assert "action_type_id" in names
    assert "action_type" not in names


async def test_the_action_type_routes_are_documented_with_their_responses(api: Api) -> None:
    """Scenario: /api/v1/action-types의 4개 엔드포인트와 오류 응답이 문서화되어 있다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    paths = spec_of(response)["paths"]
    assert set(paths["/api/v1/action-types"]) == {"get", "post"}
    assert set(paths["/api/v1/action-types/{type_id}"]) == {"patch", "delete"}
    assert "201" in paths["/api/v1/action-types"]["post"]["responses"]
    assert {"401", "403", "409", "422"} <= set(paths["/api/v1/action-types"]["post"]["responses"])
    patch_responses = paths["/api/v1/action-types/{type_id}"]["patch"]["responses"]
    assert {"401", "403", "404", "409", "422"} <= set(patch_responses)
    delete_responses = paths["/api/v1/action-types/{type_id}"]["delete"]["responses"]
    assert {"204", "401", "403", "404", "409"} <= set(delete_responses)
