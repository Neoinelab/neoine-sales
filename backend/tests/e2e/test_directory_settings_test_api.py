"""AD 설정 연결 테스트 API와 비밀번호 비노출 (SET-4·6·8, AUTH-7, T-E29·E31)."""

import logging
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.principal import Role
from tests.e2e.conftest import new_client, principal_for
from tests.e2e.payloads_auth import (
    SETTINGS,
    SETTINGS_TEST,
    problem_type,
    settings_test_payload,
    settings_update_payload,
)
from tests.factories_auth import WRONG_PASSWORD
from tests.fakes.auth_stack import MAX_PER_ACCOUNT

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

NEW_DN = "dc=new,dc=test"
SECRET = "S3cret-Dummy-pw!"  # noqa: S105 - 가짜 값. 응답·로그 누출 검사에 쓴다


async def test_test_endpoint_reports_success_without_saving(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    response = await admin_client.post(SETTINGS_TEST, json=settings_test_payload(base_dn=NEW_DN))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"success", "stage", "message"}
    assert (body["success"], body["stage"]) == (True, None)
    assert body["message"]
    (call,) = use_cases.directory.authenticate_calls
    assert (call.login_id.value, call.settings.base_dn) == ("root", NEW_DN)
    kept = (await admin_client.get(SETTINGS)).json()
    assert (kept["revision"], kept["base_dn"], kept["updated_by"]) == (1, "dc=corp,dc=test", None)


async def test_test_endpoint_reports_a_wrong_password_as_a_failed_result_not_an_error(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.post(
        SETTINGS_TEST, json=settings_test_payload(password=WRONG_PASSWORD)
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["success"], body["stage"]) == (False, "bind")
    assert body["message"]
    assert WRONG_PASSWORD not in response.text


@pytest.mark.parametrize(
    ("error", "stage"),
    [
        (DirectoryUnavailableError(stage=VerificationStage.CONNECT), "connect"),
        (DirectoryUnavailableError(stage=VerificationStage.TLS), "tls"),
        (DirectoryMisconfiguredError(stage=VerificationStage.SEARCH), "search"),
        (InvalidCredentialsError(stage=VerificationStage.BIND), "bind"),
    ],
)
async def test_test_endpoint_reports_each_failure_stage(
    admin_client: AsyncClient, use_cases: FakeUseCases, error: Exception, stage: str
) -> None:
    use_cases.directory.fail_with = error  # type: ignore[assignment]

    response = await admin_client.post(SETTINGS_TEST, json=settings_test_payload())

    assert response.status_code == 200
    assert (response.json()["success"], response.json()["stage"]) == (False, stage)


async def test_test_endpoint_without_a_password_is_422(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    response = await admin_client.post(SETTINGS_TEST, json=settings_test_payload(password=None))

    assert response.status_code == 422
    assert problem_type(response.json()) == "invalid-value"
    assert use_cases.directory.authenticate_calls == []


@pytest.mark.parametrize(
    "overrides",
    [{"server_urls": []}, {"base_dn": ""}, {"receive_timeout_seconds": 0}, {"unknown": 1}],
)
async def test_test_endpoint_rejects_invalid_settings_with_422(
    admin_client: AsyncClient, use_cases: FakeUseCases, overrides: dict[str, Any]
) -> None:
    response = await admin_client.post(SETTINGS_TEST, json=settings_test_payload(**overrides))

    assert response.status_code == 422
    assert problem_type(response.json()) in {"invalid-value", "request-validation"}
    assert use_cases.directory.authenticate_calls == []


async def test_test_endpoint_attempts_are_limited_per_admin_account(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    for _ in range(MAX_PER_ACCOUNT):
        await admin_client.post(SETTINGS_TEST, json=settings_test_payload(password=WRONG_PASSWORD))
    calls = len(use_cases.directory.authenticate_calls)

    response = await admin_client.post(SETTINGS_TEST, json=settings_test_payload())

    assert response.status_code == 429
    assert problem_type(response.json()) == "too-many-attempts"
    assert len(use_cases.directory.authenticate_calls) == calls


async def test_a_dev_login_admin_test_only_probes(app: FastAPI, use_cases: FakeUseCases) -> None:
    token = await use_cases.issue_session_for(principal_for("dev:admin", Role.ADMIN))
    async with new_client(app, token=token) as dev_admin:
        response = await dev_admin.post(SETTINGS_TEST, json=settings_test_payload(password=None))

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(use_cases.directory.probe_calls) == 1
    assert use_cases.directory.authenticate_calls == []


async def test_test_endpoint_requires_the_csrf_header(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    token = await use_cases.login_as(principal_for("root", Role.ADMIN))
    async with new_client(app, token=token, csrf=False) as bare:
        response = await bare.post(SETTINGS_TEST, json=settings_test_payload())

    assert (response.status_code, problem_type(response.json())) == (403, "csrf")


async def test_settings_responses_and_errors_never_echo_the_password(
    admin_client: AsyncClient, use_cases: FakeUseCases, caplog: pytest.LogCaptureFixture
) -> None:
    use_cases.directory.add_account("root", SECRET)
    caplog.set_level(logging.DEBUG)
    bodies = [
        await admin_client.put(SETTINGS, json=settings_update_payload(password=SECRET)),
        await admin_client.put(SETTINGS, json=settings_update_payload(2, password="x" + SECRET)),
        await admin_client.put(SETTINGS, json=settings_update_payload(2, password="p" * 300)),
        await admin_client.put(SETTINGS, json=settings_update_payload(9, password=SECRET)),
        await admin_client.post(SETTINGS_TEST, json=settings_test_payload(password=SECRET)),
        await admin_client.post(SETTINGS_TEST, json=settings_test_payload(password="x" + SECRET)),
        await admin_client.post(SETTINGS_TEST, json=settings_test_payload(password="p" * 300)),
        await admin_client.get(SETTINGS),
    ]

    assert [r.status_code for r in bodies] == [200, 422, 422, 409, 200, 200, 422, 200]
    for response in bodies:
        assert SECRET not in response.text
        assert "p" * 300 not in response.text
        assert SECRET not in "".join(response.headers.values())
        body = response.json()
        assert not any("password" in key.lower() for key in body)
        assert all("input" not in err for err in body.get("errors") or [])
    assert SECRET not in caplog.text
    assert "p" * 300 not in caplog.text
