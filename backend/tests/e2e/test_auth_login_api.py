"""POST /api/v1/auth/login (AUTH-1~9·13, THR-1·2, T-E1~E13)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, LOGIN_FAILED
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId
from app.main import create_app
from tests.e2e.conftest import SESSION_COOKIE, make_settings, new_client
from tests.e2e.payloads_auth import LOGIN, ME, credentials, problem_type
from tests.fakes.auth_stack import MAX_PER_ACCOUNT, MAX_PER_IP

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient, Response

    from tests.fakes.use_cases import FakeUseCases

LEAK = "ldap-server-internal-detail"
PROBLEM = "application/problem+json"
FAILED_BODY = {
    "type": "https://neoine-sales.example/problems/unauthenticated",
    "title": "Unauthenticated",
    "status": 401,
    "detail": LOGIN_FAILED,
    "instance": LOGIN,
}


def _cookie(response: Response, name: str = SESSION_COOKIE) -> str:
    found = [h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}=")]
    assert found, f"{name} 쿠키가 없다: {response.headers.get_list('set-cookie')}"
    return found[0]


@pytest.mark.usefixtures("ready")
async def test_login_signs_in_with_an_http_only_lax_cookie(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.post(LOGIN, json=credentials())

    assert response.status_code == 200
    assert response.json() == {
        "subject": "kim",
        "email": "kim@corp.test",
        "name": "김영업",
        "role": "sales",
    }
    cookie = _cookie(response).lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=28800" in cookie
    assert "path=/" in cookie
    assert "secure" not in cookie.replace("samesite", "")  # 기본 설정(cookie_secure=false)
    assert (await anonymous_client.get(ME)).json()["subject"] == "kim"


@pytest.mark.usefixtures("ready")
async def test_login_never_sets_the_legacy_login_cookie(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.post(LOGIN, json=credentials())

    assert not [h for h in response.headers.get_list("set-cookie") if "neoine_login" in h]


async def test_login_cookie_is_secure_when_the_setting_says_so(ready: FakeUseCases) -> None:
    app = create_app(settings=make_settings(cookie_secure=True), use_cases=ready)
    async with new_client(app, base_url="https://test") as http:
        response = await http.post(LOGIN, json=credentials())

    assert "secure" in _cookie(response).lower().split("; ")


@pytest.mark.usefixtures("ready")
async def test_login_normalizes_the_login_id(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.post(LOGIN, json=credentials(" KIM "))

    assert response.status_code == 200
    assert response.json()["subject"] == "kim"


async def test_login_updates_last_login_in_the_users_table(
    anonymous_client: AsyncClient, ready: FakeUseCases
) -> None:
    await anonymous_client.post(LOGIN, json=credentials())

    user = await ready.uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.last_login_at is not None


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "attempt",
    [
        credentials("kim", "wrong-password"),
        credentials("ghost", "pw-ghost"),
        credentials("newbie", "pw-newbie"),
        credentials("kim)(uid=*", "pw-kim"),
        credentials("kim", ""),
        credentials("kim", "   "),
        credentials("kim", "pw\u0000kim"),
    ],
    ids=["wrong", "not-in-ad", "unregistered", "malformed-id", "empty", "blank", "nul"],
)
async def test_every_failure_has_the_same_401_and_no_cookie(
    anonymous_client: AsyncClient, ready: FakeUseCases, attempt: dict[str, str]
) -> None:
    response = await anonymous_client.post(LOGIN, json=attempt)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json() == FAILED_BODY
    assert response.headers.get_list("set-cookie") == []
    assert (await anonymous_client.get(ME)).status_code == 401


async def test_deleted_user_gets_the_same_401(
    anonymous_client: AsyncClient, ready: FakeUseCases
) -> None:
    ready.directory.add_account("gone", "pw-gone")
    await ready.seed_user("gone")
    async with ready.uow as uow:
        user = await uow.users.get_active_by_login_id(LoginId("gone"))
        assert user is not None
        await uow.users.delete(user.id)
        await uow.commit()

    response = await anonymous_client.post(LOGIN, json=credentials("gone", "pw-gone"))

    assert response.json() == FAILED_BODY


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize("password", ["", "   ", "pw\u0000x"])
async def test_empty_or_nul_password_never_reaches_the_directory(
    anonymous_client: AsyncClient, ready: FakeUseCases, password: str
) -> None:
    await anonymous_client.post(LOGIN, json=credentials("kim", password))

    assert ready.directory.authenticate_calls == []


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "error",
    [
        DirectoryUnavailableError(LEAK, stage=VerificationStage.CONNECT),
        DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS),
        DirectoryMisconfiguredError(LEAK, stage=VerificationStage.SEARCH),
    ],
    ids=["connect", "tls", "misconfigured"],
)
async def test_directory_outage_is_503_with_a_fixed_message(
    anonymous_client: AsyncClient, ready: FakeUseCases, error: DirectoryUnavailableError
) -> None:
    ready.directory.fail_with = error

    response = await anonymous_client.post(LOGIN, json=credentials())

    body = response.json()
    assert response.status_code == 503
    assert problem_type(body) == "directory-unavailable"
    assert LEAK not in response.text
    assert response.headers.get_list("set-cookie") == []
    assert body["detail"]


async def test_directory_outage_message_is_identical_for_every_cause(
    anonymous_client: AsyncClient, ready: FakeUseCases
) -> None:
    details = set()
    for stage in (VerificationStage.CONNECT, VerificationStage.TLS):
        ready.directory.fail_with = DirectoryUnavailableError(LEAK, stage=stage)
        details.add((await anonymous_client.post(LOGIN, json=credentials())).json()["detail"])
    ready.directory.fail_with = DirectoryMisconfiguredError(LEAK, stage=VerificationStage.SEARCH)
    details.add((await anonymous_client.post(LOGIN, json=credentials())).json()["detail"])

    assert len(details) == 1


async def test_login_before_directory_setup_is_409_without_calling_the_directory(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    response = await anonymous_client.post(LOGIN, json=credentials())

    body = response.json()
    assert response.status_code == 409
    assert problem_type(body) == "invalid-state"
    assert body["detail"] == DIRECTORY_NOT_CONFIGURED
    assert use_cases.directory.authenticate_calls == []


@pytest.mark.usefixtures("ready")
async def test_account_lock_returns_429_without_calling_the_directory(
    anonymous_client: AsyncClient, ready: FakeUseCases
) -> None:
    for _ in range(MAX_PER_ACCOUNT):
        await anonymous_client.post(LOGIN, json=credentials("kim", "wrong"))
    calls_before = len(ready.directory.authenticate_calls)

    response = await anonymous_client.post(LOGIN, json=credentials())

    assert response.status_code == 429
    assert response.headers["content-type"].startswith(PROBLEM)
    assert problem_type(response.json()) == "too-many-attempts"
    assert response.headers.get_list("set-cookie") == []
    assert len(ready.directory.authenticate_calls) == calls_before


@pytest.mark.usefixtures("ready")
async def test_ip_lock_returns_429_even_for_a_new_account(
    anonymous_client: AsyncClient,
) -> None:
    for number in range(MAX_PER_IP):
        await anonymous_client.post(LOGIN, json=credentials(f"user{number}", "wrong"))

    response = await anonymous_client.post(LOGIN, json=credentials("kim", "pw-kim"))

    assert response.status_code == 429
    assert problem_type(response.json()) == "too-many-attempts"


@pytest.mark.usefixtures("ready")
async def test_login_needs_the_csrf_header(app: FastAPI, use_cases: FakeUseCases) -> None:
    async with new_client(app, csrf=False) as http:
        response = await http.post(LOGIN, json=credentials())

    assert response.status_code == 403
    assert problem_type(response.json()) == "csrf"
    assert use_cases.directory.authenticate_calls == []
