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
