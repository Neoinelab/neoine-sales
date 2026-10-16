"""Feature: API 계약 파일(backend/openapi.json)은 실제 앱이 공개하는 계약과 항상 같다.

API를 바꾸면 `scripts/export_openapi.py`로 파일을 갱신하고 프런트엔드 타입을 다시 생성한다.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.openapi_checks import (
    then_contact_delete_documents_the_409,
    then_contact_search_params_document_max_length,
    then_deal_search_text_params_document_max_length,
    then_every_endpoint_documents_its_error_responses,
    then_retired_customer_and_partner_paths_are_not_documented,
)
from tests.functional.steps.platform import spec_of, when_fetch_openapi

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
COMMITTED = Path(__file__).resolve().parents[3] / "openapi.json"


async def test_committed_openapi_matches_the_application(api: Api) -> None:
    """Scenario: 커밋된 openapi.json은 실행 중인 앱이 공개한 계약과 똑같다."""
    # Given
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    # When
    response = await when_fetch_openapi(api)
    # Then
    assert spec_of(response) == committed, (
        "API가 바뀌었습니다. `uv run python scripts/export_openapi.py`로 openapi.json을 갱신하세요."
    )


async def test_every_endpoint_documents_its_error_responses(api: Api) -> None:
    """Scenario: 인증 API를 뺀 모든 엔드포인트가 401(그리고 입력이 있으면 422) 응답을 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_every_endpoint_documents_its_error_responses(response)


async def test_deal_search_text_params_document_max_length(api: Api) -> None:
    """Scenario: Deal 검색의 텍스트 파라미터(keyword, vendor)는 최대 길이 100을 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_deal_search_text_params_document_max_length(response)


async def test_contact_search_params_document_max_length(api: Api) -> None:
    """Scenario: 연락처 검색 파라미터와 keyword 최대 길이(100)가 문서화된다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_contact_search_params_document_max_length(response)


async def test_retired_customer_and_partner_paths_are_not_documented(api: Api) -> None:
    """Scenario: 폐지된 고객·파트너 경로는 문서에 없고 contacts 경로가 있다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_retired_customer_and_partner_paths_are_not_documented(response)


async def test_deal_endpoints_use_the_code_path_and_share_the_deals_tag(api: Api) -> None:
    """Scenario: Deal 엔드포인트는 code 경로이고 deals 태그로 묶이며 폐지 경로는 문서에 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    paths = spec_of(response)["paths"]
    expected = {
        "/api/v1/deals": {"get", "post"},
        "/api/v1/deals/{code}": {"get", "patch", "delete"},
        "/api/v1/deals/{code}/history": {"get"},
        "/api/v1/deals/{code}/changes": {"post"},
        "/api/v1/deals/{code}/deletion-impact": {"get"},
        "/api/v1/deals/facets": {"get"},
    }
    for path, methods in expected.items():
        assert set(paths[path]) == methods, path
        for operation in paths[path].values():
            assert operation["tags"] == ["deals"], path
    retired = (
        "/api/v1/deals/{deal_id}",
        "/api/v1/deals/by-code/{code}",
        "/api/v1/deals/{deal_id}/stage",
        "/api/v1/deals/{deal_id}/stage-changes",
        "/api/v1/deals/pipeline",
    )
    assert not set(retired) & set(paths)


async def test_deal_delete_documents_its_confirmation_and_error_responses(api: Api) -> None:
    """Scenario: Deal 삭제는 confirm_code 필수 쿼리와 403·404·422 응답을 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    operation = spec_of(response)["paths"]["/api/v1/deals/{code}"]["delete"]
    parameters = {p["name"]: p for p in operation["parameters"]}
    assert parameters["confirm_code"]["required"] is True
    assert {"204", "403", "404", "422"} <= set(operation["responses"])


async def test_contact_delete_documents_the_409_for_referencing_deals(api: Api) -> None:
    """Scenario: 연락처 삭제는 참조하는 Deal이 있을 때의 409 응답을 문서화한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_contact_delete_documents_the_409(response)
