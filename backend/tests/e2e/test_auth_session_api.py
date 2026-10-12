"""세션 기반 접근: 보호된 API, 쿠키, CSRF, /auth/me, 로그아웃, dev-login, 삭제 즉시 차단.

(AUTH-8~12, T-E1~E12 중 세션 쪽)
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.main import create_app
from tests.e2e.conftest import (
    DEFAULT_LOGIN,
    SESSION_COOKIE,
    make_settings,
    new_client,
    principal_for,
)
from tests.e2e.payloads_auth import CONFIG, ME
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from httpx import AsyncClient, Response

PROBLEM = "application/problem+json"
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"
PROTECTED = [
    "/api/v1/customers",
    "/api/v1/partners",
    "/api/v1/deals",
    "/api/v1/deals/pipeline",
    f"/api/v1/deals/{UNKNOWN_ID}/stage-changes",
    "/api/v1/deal-actions",
    ME,
]
DEV_LOGIN = "/api/v1/auth/dev-login"
LOGOUT = "/api/v1/auth/logout"


def _cookie_header(response: Response, name: str) -> str:
    headers = [h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}=")]
    assert headers, f"{name} 쿠키가 설정되지 않았다: {response.headers.get_list('set-cookie')}"
    return headers[0]


@pytest.mark.parametrize("path", PROTECTED)
async def test_protected_endpoints_require_a_session(
    anonymous_client: AsyncClient, path: str
) -> None:
    response = await anonymous_client.get(path)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("unauthenticated")


async def test_write_endpoints_are_protected_too(anonymous_client: AsyncClient) -> None:
    assert (await anonymous_client.post("/api/v1/customers", json={})).status_code == 401
    assert (await anonymous_client.delete(f"/api/v1/deals/{UNKNOWN_ID}")).status_code == 401
    stage = await anonymous_client.post(
        f"/api/v1/deals/{UNKNOWN_ID}/stage", json={"stage": "introduction"}
    )
    assert stage.status_code == 401


async def test_unknown_or_expired_session_cookie_is_unauthenticated(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    fake_token = "made-up-token"  # noqa: S105
    async with new_client(app, token=fake_token) as http:
        assert (await http.get("/api/v1/customers")).status_code == 401
    token = await use_cases.login_as(principal_for("kim"))
    use_cases.clock.advance(9 * 3600)
    async with new_client(app, token=token) as http:
        assert (await http.get("/api/v1/customers")).status_code == 401


async def test_health_and_auth_config_are_public(anonymous_client: AsyncClient) -> None:
    assert (await anonymous_client.get("/healthz")).status_code == 200
    assert (await anonymous_client.get("/readyz")).status_code == 200
    assert (await anonymous_client.get(CONFIG)).status_code == 200


async def test_me_returns_the_signed_in_user(client: AsyncClient) -> None:
    body = (await client.get(ME)).json()

    assert body["role"] == "sales"
    assert body["subject"] == DEFAULT_LOGIN
    assert set(body) == {"subject", "email", "name", "role"}


async def test_unsafe_requests_need_the_csrf_header(app: FastAPI, use_cases: FakeUseCases) -> None:
    token = await use_cases.login_as(principal_for("kim"))
    async with new_client(app, token=token, csrf=False) as http:
        read = await http.get("/api/v1/customers")
        write = await http.post(
            "/api/v1/customers", json={"company_name": "a", "contact_name": "b"}
        )

    assert read.status_code == 200
    assert write.status_code == 403
    assert write.json()["type"].endswith("csrf")


async def test_stage_change_needs_the_csrf_header(app: FastAPI, use_cases: FakeUseCases) -> None:
    token = await use_cases.login_as(principal_for("kim"))
    async with new_client(app, token=token, csrf=False) as http:
        write = await http.post(f"/api/v1/deals/{UNKNOWN_ID}/stage", json={"stage": "introduction"})

    assert write.status_code == 403
    assert write.json()["type"].endswith("csrf")


@pytest.mark.parametrize("role", list(Role))
async def test_logout_revokes_the_session_for_every_role(
    client_as: Callable[[str, Role], Awaitable[AsyncClient]], role: Role
) -> None:
    http = await client_as("someone", role)

    response = await http.post(LOGOUT)

    assert response.status_code == 204
    assert "max-age=0" in _cookie_header(response, SESSION_COOKIE).lower()
    assert (await http.get(ME)).status_code == 401


async def test_logout_without_a_session_is_harmless(anonymous_client: AsyncClient) -> None:
    assert (await anonymous_client.post(LOGOUT)).status_code == 204


@pytest.mark.parametrize("role", list(Role))
async def test_me_works_for_every_role(
    client_as: Callable[[str, Role], Awaitable[AsyncClient]], role: Role
) -> None:
    http = await client_as("someone", role)

    assert (await http.get(ME)).json()["role"] == role.value


async def test_deleted_users_session_is_rejected_from_the_next_request(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    assert (await client.get("/api/v1/customers")).status_code == 200
    async with use_cases.uow as uow:
        user = await uow.users.get_active_by_login_id(LoginId(DEFAULT_LOGIN))
        assert user is not None
        user.soft_delete(use_cases.clock.now())
        await uow.users.update(user)
        await uow.commit()

    assert (await client.get("/api/v1/customers")).status_code == 401
    assert (await client.get(ME)).status_code == 401


async def test_role_change_in_the_users_table_applies_immediately(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    async with use_cases.uow as uow:
        user = await uow.users.get_active_by_login_id(LoginId(DEFAULT_LOGIN))
        assert user is not None
        user.role = Role.ADMIN
        await uow.users.update(user)
        await uow.commit()

    assert (await client.get(ME)).json()["role"] == "admin"


async def test_session_of_a_subject_missing_from_the_users_table_is_rejected(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    token = await use_cases.issue_session_for(principal_for("ghost"))
    async with new_client(app, token=token) as http:
        assert (await http.get(ME)).status_code == 401


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_dev_login_signs_in_with_each_role(anonymous_client: AsyncClient, role: str) -> None:
    response = await anonymous_client.post(DEV_LOGIN, json={"role": role})

    assert response.status_code == 200
    assert response.json()["role"] == role
    assert response.json()["subject"] == f"dev:{role}"
    assert (await anonymous_client.get(ME)).json()["role"] == role


async def test_dev_login_rejects_unknown_roles(anonymous_client: AsyncClient) -> None:
    assert (await anonymous_client.post(DEV_LOGIN, json={"role": "root"})).status_code == 422


async def test_dev_login_does_not_exist_when_disabled(use_cases: FakeUseCases) -> None:
    app = create_app(settings=make_settings(dev_login_enabled=False), use_cases=use_cases)
    async with new_client(app) as http:
        response = await http.post(DEV_LOGIN, json={"role": "admin"})
        config = await http.get(CONFIG)

    assert response.status_code == 404
    assert config.json()["dev_login"] is False


async def test_dev_sessions_are_rejected_when_dev_login_is_not_allowed() -> None:
    use_cases = FakeUseCases(allow_dev_sessions=False)
    settings = make_settings(dev_login_enabled=False)
    app = create_app(settings=settings, use_cases=use_cases)
    token = (await use_cases.dev_login().execute(Role.ADMIN)).token

    async with new_client(app, token=token) as http:
        assert (await http.get(ME)).status_code == 401
        assert (await http.get("/api/v1/customers")).status_code == 401
