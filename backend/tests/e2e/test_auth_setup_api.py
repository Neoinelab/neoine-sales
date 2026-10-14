"""최초 설정 2단계 API (SETUP-1~8, DS-2~5, T-E14~E19)."""

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from app.application.auth.messages import DIRECTORY_FIRST, SETUP_CLOSED
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from tests.e2e.conftest import SESSION_COOKIE, new_client
from tests.e2e.payloads_auth import (
    CONFIG,
    ME,
    SETUP,
    SETUP_DIRECTORY,
    credentials,
    directory_payload,
    problem_type,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

LEAK = "internal-ldap-server-banner"
PROBLEM = "application/problem+json"
SETTINGS_KEYS = {
    "server_urls",
    "use_starttls",
    "ca_cert_pem",
    "bind_template",
    "base_dn",
    "user_filter",
    "display_name_attribute",
    "email_attribute",
    "connect_timeout_seconds",
    "receive_timeout_seconds",
    "revision",
    "updated_at",
    "updated_by",
}


async def _flags(client: AsyncClient) -> tuple[bool, bool]:
    body = (await client.get(CONFIG)).json()
    return body["needs_directory_setup"], body["needs_admin_setup"]


async def test_two_step_setup_signs_in_as_admin(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    use_cases.directory.add_account("kim", "pw-kim", display_name="김관리", email="kim@corp.test")
    assert await _flags(anonymous_client) == (True, False)

    saved = await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())
    assert saved.status_code == 200
    assert await _flags(anonymous_client) == (False, True)
    done = await anonymous_client.post(SETUP, json=credentials())

    assert done.status_code == 200
    body = done.json()
    assert str(UUID(body.pop("user_id")))
    assert body == {
        "subject": "kim",
        "email": "kim@corp.test",
        "name": "김관리",
        "role": "admin",
    }
    cookie = next(h for h in done.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE))
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()
    assert (await anonymous_client.get(ME)).json()["role"] == "admin"
    assert await _flags(anonymous_client) == (False, False)
    config = (await anonymous_client.get(CONFIG)).json()
    assert config["directory_login"] is True


async def test_setup_directory_returns_the_saved_settings_with_revision(
    anonymous_client: AsyncClient,
) -> None:
    response = await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())

    body = response.json()
    assert set(body) == SETTINGS_KEYS
    assert (body["revision"], body["updated_by"]) == (1, None)
    assert body["server_urls"] == ["ldaps://dc1.corp.test"]
    assert body["base_dn"] == directory_payload()["base_dn"]


async def test_setup_directory_can_be_overwritten_before_the_first_admin(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())

    second = await anonymous_client.put(
        SETUP_DIRECTORY, json=directory_payload(base_dn="dc=other,dc=test")
    )

    assert second.status_code == 200
    assert second.json()["revision"] == 2
    assert second.json()["base_dn"] == "dc=other,dc=test"
    assert len(use_cases.directory.probe_calls) == 2


async def test_setup_directory_requires_no_session(
    anonymous_client: AsyncClient,
) -> None:
    assert (await anonymous_client.get(ME)).status_code == 401

    response = await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())

    assert response.status_code == 200


async def test_setup_endpoints_close_after_the_first_admin(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_directory()
    await use_cases.seed_user("boss", Role.ADMIN)
    use_cases.directory.add_account("kim", "pw-kim")

    put = await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())
    post = await anonymous_client.post(SETUP, json=credentials())

    for response in (put, post):
        assert response.status_code == 409
        assert problem_type(response.json()) == "invalid-state"
        assert response.json()["detail"] == SETUP_CLOSED
        assert SESSION_COOKIE not in response.headers.get("set-cookie", "")
    assert use_cases.directory.probe_calls == []
    assert use_cases.directory.authenticate_calls == []
    assert await _flags(anonymous_client) == (False, False)


async def test_setup_stays_closed_after_the_setup_admin_is_registered(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    use_cases.directory.add_account("kim", "pw-kim")
    await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())
    await anonymous_client.post(SETUP, json=credentials())
    use_cases.directory.add_account("mallory", "pw-mallory")

    again = await anonymous_client.post(SETUP, json=credentials("mallory", "pw-mallory"))
    overwrite = await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())

    assert again.status_code == overwrite.status_code == 409
    assert await use_cases.uow.users.get_active_by_login_id(LoginId("mallory")) is None


async def test_setup_admin_before_directory_is_409_without_calling_the_directory(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    use_cases.directory.add_account("kim", "pw-kim")

    response = await anonymous_client.post(SETUP, json=credentials())

    assert response.status_code == 409
    assert problem_type(response.json()) == "invalid-state"
    assert response.json()["detail"] == DIRECTORY_FIRST
    assert use_cases.directory.authenticate_calls == []


@pytest.mark.parametrize("method", ["put", "post"])
async def test_setup_requests_need_the_csrf_header(
    app: FastAPI, use_cases: FakeUseCases, method: str
) -> None:
    await use_cases.seed_directory()
    async with new_client(app, csrf=False) as http:
        if method == "put":
            response = await http.put(SETUP_DIRECTORY, json=directory_payload())
        else:
            response = await http.post(SETUP, json=credentials())

    assert response.status_code == 403
    assert problem_type(response.json()) == "csrf"
    assert use_cases.directory.probe_calls == []
    assert use_cases.directory.authenticate_calls == []


async def test_setup_admin_wrong_password_is_the_login_failure(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    use_cases.directory.add_account("kim", "pw-kim")
    await use_cases.seed_directory()

    response = await anonymous_client.post(SETUP, json=credentials("kim", "wrong"))

    assert response.status_code == 401
    assert problem_type(response.json()) == "unauthenticated"
    assert response.headers.get_list("set-cookie") == []
    assert await _flags(anonymous_client) == (False, True)
