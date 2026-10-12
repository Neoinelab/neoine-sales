"""권한 매트릭스를 경로 열거로 고정한다 (ROLE-1~5, SET-7, T-E32~E34).

EXPECTED(permission_table.py)와 앱의 실제 엔드포인트 집합이 같아야 하고, (경로, 역할)마다
허용이면 401/403이 아니고 비허용이면 403 forbidden이어야 한다. 새 엔드포인트를 추가하고
표에 넣지 않으면 test_every_api_route_is_in_the_matrix가 실패한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.e2e.payloads_auth import problem_type
from tests.e2e.permission_table import (
    ADMIN_ONLY,
    BUSINESS_WRITES,
    EXPECTED,
    concrete_path,
    protected_routes,
)
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import AsyncClient, Response

ROLES = [Role.ADMIN, Role.SALES, Role.USER]
CASES = [(route, role) for route in protected_routes() for role in ROLES]
CASE_IDS = [f"{method} {path} as {role.value}" for (method, path), role in CASES]
ROUTE_IDS = [f"{method} {path}" for method, path in protected_routes()]
WRITE_ROUTES = [*BUSINESS_WRITES]


def _openapi_routes() -> set[tuple[str, str]]:
    spec = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()
    return {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if path in {"/healthz", "/readyz"} or path.startswith("/api/v1")
    }


def _body(method: str) -> dict[str, Any] | None:
    return {} if method in {"POST", "PUT"} else None


async def _call(client: AsyncClient, method: str, path: str) -> Response:
    return await client.request(method, concrete_path(path), json=_body(method))


def test_every_api_route_is_in_the_matrix() -> None:
    actual = _openapi_routes()

    assert actual - set(EXPECTED) == set(), "권한 표(permission_table.py)에 없는 엔드포인트"
    assert set(EXPECTED) - actual == set(), "표에는 있지만 앱에 없는 엔드포인트"


def test_the_matrix_lists_each_admin_only_route_for_admins_alone() -> None:
    assert all(EXPECTED[route] == frozenset({Role.ADMIN}) for route in ADMIN_ONLY)
    assert all(Role.USER not in (EXPECTED[route] or ()) for route in WRITE_ROUTES)


@pytest.mark.parametrize("route", protected_routes(), ids=ROUTE_IDS)
async def test_anonymous_requests_to_protected_routes_are_401(
    anonymous_client: AsyncClient, route: tuple[str, str]
) -> None:
    response = await _call(anonymous_client, *route)

    assert response.status_code == 401
    assert problem_type(response.json()) == "unauthenticated"


@pytest.mark.parametrize(("route", "role"), CASES, ids=CASE_IDS)
async def test_route_access_by_role(
    client_as: Callable[[str, Role], Awaitable[AsyncClient]],
    route: tuple[str, str],
    role: Role,
) -> None:
    client = await client_as(f"{role.value}-tester", role)
    allowed = role in (EXPECTED[route] or ())

    response = await _call(client, *route)

    if allowed:
        assert response.status_code not in {401, 403}, response.text
    else:
        assert response.status_code == 403, response.text
        assert response.headers["content-type"].startswith("application/problem+json")
        assert problem_type(response.json()) == "forbidden"
        assert "권한" in response.json()["detail"]


@pytest.mark.parametrize("route", WRITE_ROUTES, ids=[f"{m} {p}" for m, p in WRITE_ROUTES])
async def test_viewer_write_is_forbidden_before_body_validation(
    viewer_client: AsyncClient, route: tuple[str, str]
) -> None:
    method, path = route

    invalid_body = await viewer_client.request(
        method,
        concrete_path(path),
        json={"unexpected": ["garbage"]} if method != "DELETE" else None,
    )
    assert invalid_body.status_code == 403
    assert problem_type(invalid_body.json()) == "forbidden"


@pytest.mark.parametrize("route", ADMIN_ONLY, ids=[f"{m} {p}" for m, p in ADMIN_ONLY])
async def test_sales_is_forbidden_on_admin_routes_before_body_validation(
    client: AsyncClient, route: tuple[str, str]
) -> None:
    method, path = route

    response = await client.request(
        method, concrete_path(path), json={"unexpected": 1} if method != "DELETE" else None
    )

    assert response.status_code == 403
    assert problem_type(response.json()) == "forbidden"
    assert "관리자" in response.json()["detail"]


@pytest.mark.parametrize("role", ROLES)
async def test_every_role_can_read_me_and_log_out(
    client_as: Callable[[str, Role], Awaitable[AsyncClient]], role: Role
) -> None:
    client = await client_as(f"{role.value}-tester", role)

    me = await client.get("/api/v1/auth/me")
    logout = await client.post("/api/v1/auth/logout")

    assert (me.status_code, me.json()["role"]) == (200, role.value)
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_unauthenticated_beats_forbidden_on_admin_and_write_routes(
    anonymous_client: AsyncClient,
) -> None:
    for method, path in [*ADMIN_ONLY, *BUSINESS_WRITES]:
        response = await _call(anonymous_client, method, path)

        assert response.status_code == 401, f"{method} {path}"
