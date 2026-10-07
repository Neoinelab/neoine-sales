"""인증: 보호된 API, 세션 쿠키, CSRF, OIDC 로그인 흐름, 로컬 전용 dev 로그인."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.main import create_app
from tests.e2e.conftest import (
    LOGIN_COOKIE,
    OIDC_SETTINGS,
    SESSION_COOKIE,
    make_settings,
    new_client,
)
from tests.fakes.identity_provider import DEFAULT_IDENTITY

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from httpx import AsyncClient, Response

    from tests.fakes.identity_provider import FakeIdentityProvider
    from tests.fakes.use_cases import FakeUseCases

PROBLEM = "application/problem+json"
PROTECTED = [
    "/api/v1/customers",
    "/api/v1/partners",
    "/api/v1/deals",
    "/api/v1/deal-actions",
    "/api/v1/auth/me",
]
CALLBACK = "/api/v1/auth/callback"
VALID_CALLBACK = {"code": "c1", "state": "fake-state"}
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


def _cookie_header(response: Response, name: str) -> str:
    headers = [h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}=")]
    assert headers, f"{name} 쿠키가 설정되지 않았다: {response.headers.get_list('set-cookie')}"
    return headers[0]


@pytest.fixture
def oidc_app(use_cases: FakeUseCases) -> FastAPI:
    return create_app(settings=make_settings(**OIDC_SETTINGS), use_cases=use_cases)


@pytest.fixture
async def oidc_client(oidc_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with new_client(oidc_app) as http:
        yield http


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


async def test_unknown_or_expired_session_cookie_is_unauthenticated(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    fake_token = "made-up-token"  # noqa: S105
    async with new_client(app, token=fake_token) as http:
        assert (await http.get("/api/v1/customers")).status_code == 401
    token = (await use_cases.dev_login().execute(Role.SALES)).token
    use_cases.clock.advance(9 * 3600)
    async with new_client(app, token=token) as http:
        assert (await http.get("/api/v1/customers")).status_code == 401


async def test_health_and_auth_config_are_public(anonymous_client: AsyncClient) -> None:
    assert (await anonymous_client.get("/healthz")).status_code == 200
    assert (await anonymous_client.get("/readyz")).status_code == 200
    config = await anonymous_client.get("/api/v1/auth/config")
    assert config.json() == {"dev_login": True, "oidc": False}


async def test_me_returns_the_signed_in_user(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/auth/me")).json()

    assert body["role"] == "sales"
    assert set(body) == {"subject", "email", "name", "role"}


async def test_unsafe_requests_need_the_csrf_header(app: FastAPI, use_cases: FakeUseCases) -> None:
    token = (await use_cases.dev_login().execute(Role.SALES)).token
    async with new_client(app, token=token, csrf=False) as http:
        read = await http.get("/api/v1/customers")
        write = await http.post(
            "/api/v1/customers", json={"company_name": "a", "contact_name": "b"}
        )

    assert read.status_code == 200
    assert write.status_code == 403
    assert write.json()["type"].endswith("csrf")


async def test_oidc_login_flow_signs_the_user_in(
    oidc_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    start = await oidc_client.get("/api/v1/auth/login")

    assert start.status_code == 302
    assert start.headers["location"] == "https://idp.example/authorize?state=fake-state"
    pending = _cookie_header(start, LOGIN_COOKIE)
    assert "HttpOnly" in pending
    assert "samesite=lax" in pending.lower()
    assert "path=/api/v1/auth" in pending.lower()

    done = await oidc_client.get(
        "/api/v1/auth/callback", params={"code": "c1", "state": "fake-state"}
    )

    assert done.status_code == 302
    assert done.headers["location"] == "/"
    session = _cookie_header(done, SESSION_COOKIE)
    assert "HttpOnly" in session
    assert "samesite=lax" in session.lower()
    assert "max-age=28800" in session.lower()
    me = (await oidc_client.get("/api/v1/auth/me")).json()
    assert me["email"] == DEFAULT_IDENTITY.email
    assert me["role"] == "sales"
    assert use_cases.identity_provider.completed == [("c1", "fake-verifier", "fake-nonce")]


@pytest.mark.parametrize(
    "params",
    [{"code": "c1", "state": "tampered"}, {"error": "access_denied"}, {"state": "fake-state"}],
    ids=["state-mismatch", "idp-error", "missing-code"],
)
async def test_failed_callback_redirects_to_login_without_a_session(
    oidc_client: AsyncClient, params: dict[str, str]
) -> None:
    await oidc_client.get("/api/v1/auth/login")

    done = await oidc_client.get("/api/v1/auth/callback", params=params)

    assert done.status_code == 302
    assert done.headers["location"] == "/login?error=auth"
    assert (await oidc_client.get("/api/v1/auth/me")).status_code == 401


async def test_callback_without_the_login_cookie_fails(oidc_client: AsyncClient) -> None:
    done = await oidc_client.get("/api/v1/auth/callback", params={"code": "c", "state": "s"})

    assert done.headers["location"] == "/login?error=auth"


async def test_idp_rejection_redirects_with_the_auth_error(
    oidc_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    use_cases.identity_provider.fail_with = AuthenticationError("검증 실패")
    await oidc_client.get("/api/v1/auth/login")

    done = await oidc_client.get(
        "/api/v1/auth/callback", params={"code": "c1", "state": "fake-state"}
    )

    assert done.headers["location"] == "/login?error=auth"


async def test_user_outside_the_mapped_groups_is_denied(
    oidc_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    identity_provider: FakeIdentityProvider = use_cases.identity_provider
    identity_provider.identity = DEFAULT_IDENTITY.__class__(
        subject="x", email=None, name="외부인", groups=frozenset({"Marketing"})
    )
    await oidc_client.get("/api/v1/auth/login")

    done = await oidc_client.get(
        "/api/v1/auth/callback", params={"code": "c1", "state": "fake-state"}
    )

    assert done.headers["location"] == "/login?error=denied"
    assert (await oidc_client.get("/api/v1/auth/me")).status_code == 401


async def test_secure_flag_follows_the_cookie_secure_setting(use_cases: FakeUseCases) -> None:
    app = create_app(
        settings=make_settings(cookie_secure=True, **OIDC_SETTINGS), use_cases=use_cases
    )
    async with new_client(app, base_url="https://test") as http:
        start = await http.get("/api/v1/auth/login")
        done = await http.get("/api/v1/auth/callback", params={"code": "c", "state": "fake-state"})

    assert "Secure" in _cookie_header(start, LOGIN_COOKIE)
    assert "Secure" in _cookie_header(done, SESSION_COOKIE)


async def test_logout_revokes_the_session_and_clears_the_cookie(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert "max-age=0" in _cookie_header(response, SESSION_COOKIE).lower()
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_logout_without_a_session_is_harmless(anonymous_client: AsyncClient) -> None:
    assert (await anonymous_client.post("/api/v1/auth/logout")).status_code == 204


async def test_login_routes_are_absent_when_oidc_is_not_configured(
    anonymous_client: AsyncClient,
) -> None:
    assert (await anonymous_client.get("/api/v1/auth/login")).status_code == 404
    assert (await anonymous_client.get("/api/v1/auth/callback")).status_code == 404


async def test_dev_login_signs_in_with_the_requested_role(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.post("/api/v1/auth/dev-login", json={"role": "admin"})

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert (await anonymous_client.get("/api/v1/auth/me")).json()["role"] == "admin"


async def test_dev_login_rejects_unknown_roles(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.post("/api/v1/auth/dev-login", json={"role": "root"})

    assert response.status_code == 422


async def test_dev_login_does_not_exist_when_disabled(use_cases: FakeUseCases) -> None:
    settings = make_settings(dev_login_enabled=False, **OIDC_SETTINGS)
    app = create_app(settings=settings, use_cases=use_cases)
    async with new_client(app) as http:
        response = await http.post("/api/v1/auth/dev-login", json={"role": "admin"})
        config = await http.get("/api/v1/auth/config")

    assert response.status_code == 404
    assert config.json() == {"dev_login": False, "oidc": True}
