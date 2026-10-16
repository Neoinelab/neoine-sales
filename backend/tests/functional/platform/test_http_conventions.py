"""Feature: 서버는 문서 노출·CORS·오류 형식(Problem)에 대해 모든 API에 공통인 규칙을 지킨다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.conftest import ALLOWED_ORIGIN
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.health import when_check_liveness
from tests.functional.steps.platform import (
    PROBLEM_CONTENT_TYPE,
    given_documentation_disabled,
    when_open,
    when_preflight,
)
from tests.functional.steps.requests import when_get, when_request

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
DOCUMENTATION_PATHS = ["/docs", "/openapi.json"]
HIDDEN_PATHS = ["/docs", "/redoc", "/openapi.json"]
MISSING_DEAL = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize("path", DOCUMENTATION_PATHS)
async def test_docs_are_served_when_enabled(api: Api, path: str) -> None:
    """Scenario: 문서 노출이 켜져 있으면 API 문서와 openapi.json을 열 수 있다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_open(api, path)
    # Then
    then_status_is(response, 200)


@pytest.mark.parametrize("path", HIDDEN_PATHS)
async def test_docs_are_hidden_when_disabled(api: Api, path: str) -> None:
    """Scenario: 문서 노출이 꺼져 있으면 문서 경로는 모두 404다."""
    # Given
    await given_documentation_disabled(api)
    # When
    response = await when_open(api, path)
    # Then
    then_status_is(response, 404)


async def test_health_stays_available_when_docs_are_disabled(api: Api) -> None:
    """Scenario: 문서를 꺼도 생존 확인(healthz)은 그대로 200이다."""
    # Given
    await given_documentation_disabled(api)
    # When
    response = await when_check_liveness(api)
    # Then
    then_status_is(response, 200)


async def test_cors_allows_the_configured_origin(api: Api) -> None:
    """Scenario: 설정된 출처의 CORS 사전 요청은 허용되고 그 출처가 응답 헤더에 돌아온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_preflight(api, origin=ALLOWED_ORIGIN)
    # Then
    then_status_is(response, 200)
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


async def test_cors_does_not_allow_other_origins(api: Api) -> None:
    """Scenario: 설정에 없는 출처의 CORS 사전 요청에는 허용 헤더가 붙지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_preflight(api, origin="https://evil.example")
    # Then
    assert "access-control-allow-origin" not in response.headers


async def test_unknown_route_is_a_404_problem(api: Api) -> None:
    """Scenario: 없는 경로는 404 Problem 문서(status 포함)로 답한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get(api, "/api/v1/nothing-here")
    # Then
    then_status_is(response, 404)
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert response.json()["status"] == 404


async def test_wrong_method_is_a_405_problem(api: Api) -> None:
    """Scenario: 허용되지 않은 HTTP 메서드는 405 Problem 문서로 답한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_request(api, "PATCH", "/api/v1/users")
    # Then
    then_status_is(response, 405)
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)


async def test_problem_documents_carry_the_request_path(api: Api) -> None:
    """Scenario: 오류 Problem 문서의 instance에는 요청한 경로가 담긴다."""
    # Given
    await given_logged_in_as(api, role="sales")
    path = f"/api/v1/deals/{MISSING_DEAL}"
    # When
    response = await when_get(api, path)
    # Then
    assert response.json()["instance"] == path
