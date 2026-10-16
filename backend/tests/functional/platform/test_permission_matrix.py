"""Feature: 모든 API 경로는 역할별 권한 표대로만 열려 있다(비로그인 401, 권한 없음 403).

기준은 `steps/permissions.py`의 표다. 새 엔드포인트를 표에 넣지 않으면 첫 시나리오가 실패한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import ME, given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.permission_checks import then_route_access_is
from tests.functional.steps.permissions import (
    ADMIN_ONLY,
    BUSINESS_WRITES,
    EXPECTED,
    ROLES,
    protected_routes,
    route_id,
    when_call_route,
    when_call_route_with_garbage_body,
)
from tests.functional.steps.platform import (
    api_routes_of,
    spec_of,
    then_problem_kind_is,
    when_fetch_openapi,
)
from tests.functional.steps.requests import then_get_is, when_get
from tests.functional.steps.session import when_log_out

if TYPE_CHECKING:
    from app.domain.auth.principal import Role
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
CASES = [(route, role) for route in protected_routes() for role in ROLES]
CASE_IDS = [f"{route_id(route)} as {role.value}" for route, role in CASES]
ROUTE_IDS = [route_id(route) for route in protected_routes()]


async def test_every_api_route_is_in_the_matrix(api: Api) -> None:
    """Scenario: 앱이 공개한 모든 엔드포인트가 권한 표에 있고, 표에는 없는 엔드포인트가 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    actual = api_routes_of(spec_of(response))
    assert actual - set(EXPECTED) == set(), "권한 표(permissions.py)에 없는 엔드포인트"
    assert set(EXPECTED) - actual == set(), "표에는 있지만 앱에 없는 엔드포인트"


@pytest.mark.parametrize("route", protected_routes(), ids=ROUTE_IDS)
async def test_anonymous_requests_to_protected_routes_are_401(
    api: Api, route: tuple[str, str]
) -> None:
    """Scenario: 로그인하지 않고 보호된 경로를 부르면 401(unauthenticated)이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_call_route(api, route)
    # Then
    then_problem_kind_is(response, status=401, kinds=("unauthenticated",))


@pytest.mark.parametrize(("route", "role"), CASES, ids=CASE_IDS)
async def test_route_access_by_role(api: Api, route: tuple[str, str], role: Role) -> None:
    """Scenario: 허용된 역할에는 경로가 열리고(401/403 아님) 아닌 역할에는 403(forbidden)이다."""
    # Given
    await given_logged_in_as(api, role=role.value)
    allowed = role in (EXPECTED[route] or ())
    # When
    response = await when_call_route(api, route)
    # Then
    then_route_access_is(response, allowed=allowed)


@pytest.mark.parametrize("route", BUSINESS_WRITES, ids=[route_id(r) for r in BUSINESS_WRITES])
async def test_viewer_write_is_forbidden_before_body_validation(
    api: Api, route: tuple[str, str]
) -> None:
    """Scenario: 조회 전용(user) 역할이 잘못된 본문으로 쓰기를 시도해도 검증보다 먼저 403이다."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_call_route_with_garbage_body(api, route)
    # Then
    then_problem_kind_is(response, status=403, kinds=("forbidden",))


@pytest.mark.parametrize("route", ADMIN_ONLY, ids=[route_id(r) for r in ADMIN_ONLY])
async def test_sales_is_forbidden_on_admin_routes_before_body_validation(
    api: Api, route: tuple[str, str]
) -> None:
    """Scenario: sales가 잘못된 본문으로 관리자 경로를 불러도 검증보다 먼저 403(관리자 전용)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_call_route_with_garbage_body(api, route)
    # Then
    then_problem_kind_is(response, status=403, kinds=("forbidden",))
    assert "관리자" in response.json()["detail"]


@pytest.mark.parametrize("role", ROLES, ids=[r.value for r in ROLES])
async def test_every_role_can_read_me(api: Api, role: Role) -> None:
    """Scenario: 어느 역할이든 로그인하면 내 정보 조회가 자기 역할을 돌려준다."""
    # Given
    await given_logged_in_as(api, role=role.value)
    # When
    response = await when_get(api, ME)
    # Then
    then_status_is(response, 200)
    assert response.json()["role"] == role.value


@pytest.mark.parametrize("role", ROLES, ids=[r.value for r in ROLES])
async def test_every_role_can_log_out(api: Api, role: Role) -> None:
    """Scenario: 어느 역할이든 로그아웃하면 204이고 그 뒤에는 내 정보 조회가 401이다."""
    # Given
    await given_logged_in_as(api, role=role.value)
    # When
    response = await when_log_out(api)
    # Then
    then_status_is(response, 204)
    await then_get_is(api, ME, 401)
