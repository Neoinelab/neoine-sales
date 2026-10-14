"""AD 설정 저장 정책: 시도 제한·CSRF·dev 로그인·세션·다음 로그인 (SET-5·6, AUTH-14, T-E30)."""

from typing import TYPE_CHECKING

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.principal import Role
from tests.e2e.conftest import new_client, principal_for
from tests.e2e.payloads_auth import (
    LOGIN,
    SETTINGS,
    credentials,
    problem_type,
    settings_update_payload,
)
from tests.factories_auth import WRONG_PASSWORD
from tests.fakes.auth_stack import MAX_PER_ACCOUNT

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

NEW_DN = "dc=new,dc=test"


async def test_update_attempts_are_limited_per_admin_account(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    for _ in range(MAX_PER_ACCOUNT):
        await admin_client.put(SETTINGS, json=settings_update_payload(password=WRONG_PASSWORD))
    calls = len(use_cases.directory.authenticate_calls)

    response = await admin_client.put(SETTINGS, json=settings_update_payload(base_dn=NEW_DN))

    assert response.status_code == 429
    assert problem_type(response.json()) == "too-many-attempts"
    assert len(use_cases.directory.authenticate_calls) == calls


async def test_update_requires_the_csrf_header(app: FastAPI, use_cases: FakeUseCases) -> None:
    await use_cases.seed_directory()
    token = await use_cases.login_as(principal_for("root", Role.ADMIN))
    async with new_client(app, token=token, csrf=False) as bare:
        response = await bare.put(SETTINGS, json=settings_update_payload())

    assert (response.status_code, problem_type(response.json())) == (403, "csrf")


async def test_a_dev_login_admin_saves_after_a_probe_only_check(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_directory()
    token = (await use_cases.dev_login().execute(Role.ADMIN)).token
    async with new_client(app, token=token) as dev_admin:
        response = await dev_admin.put(
            SETTINGS, json=settings_update_payload(password=None, base_dn=NEW_DN)
        )

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["updated_by"]["id"] == str(await use_cases.user_id_of("dev-admin"))
    assert response.json()["updated_by"]["name"] == "개발 사용자(admin)"  # UserRef(users 행)
    assert "login_id" not in response.json()["updated_by"]
    assert len(use_cases.directory.probe_calls) == 1
    assert use_cases.directory.authenticate_calls == []


async def test_a_dev_login_admin_update_fails_422_when_the_probe_fails(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_directory()
    use_cases.directory.probe_fails_with = DirectoryUnavailableError(
        stage=VerificationStage.CONNECT
    )
    token = (await use_cases.dev_login().execute(Role.ADMIN)).token
    async with new_client(app, token=token) as dev_admin:
        response = await dev_admin.put(SETTINGS, json=settings_update_payload(password=None))

    assert response.status_code == 422
    assert response.json()["stage"] == "connect"


async def test_changing_settings_keeps_every_existing_session(
    admin_client: AsyncClient, client_as: Callable[[str, Role], Awaitable[AsyncClient]]
) -> None:
    kim = await client_as("kim", Role.SALES)

    await admin_client.put(SETTINGS, json=settings_update_payload(base_dn=NEW_DN))

    assert (await kim.get("/api/v1/customers")).status_code == 200
    assert (await admin_client.get(SETTINGS)).status_code == 200


async def test_new_settings_apply_to_the_next_login(
    admin_client: AsyncClient, anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)
    use_cases.directory.add_account("kim", "pw-kim")
    await admin_client.put(SETTINGS, json=settings_update_payload(base_dn=NEW_DN))
    use_cases.directory.authenticate_calls.clear()

    login = await anonymous_client.post(LOGIN, json=credentials())

    assert login.status_code == 200
    (call,) = use_cases.directory.authenticate_calls
    assert (call.login_id.value, call.settings.base_dn) == ("kim", NEW_DN)
