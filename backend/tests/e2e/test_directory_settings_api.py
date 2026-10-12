"""AD 설정 관리 API 조회·저장 검증 (SET-1~3·5·6, T-E26~E28)."""

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
    directory_payload,
    problem_type,
    settings_update_payload,
)
from tests.factories_auth import WRONG_PASSWORD

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

PROBLEM = "application/problem+json"
FIELDS = {
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
NEW_DN = "dc=new,dc=test"


async def test_admin_reads_the_current_settings(admin_client: AsyncClient) -> None:
    response = await admin_client.get(SETTINGS)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == FIELDS
    assert {k: v for k, v in body.items() if k in directory_payload()} == directory_payload()
    assert (body["revision"], body["updated_by"]) == (1, None)
    assert body["updated_at"].startswith("2026-01-01T09:00:")
    assert not any("password" in key.lower() or "secret" in key.lower() for key in body)


async def test_reading_settings_before_any_are_saved_is_404(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    token = await use_cases.login_as(principal_for("root", Role.ADMIN))
    async with new_client(app, token=token) as admin:
        response = await admin.get(SETTINGS)

    assert response.status_code == 404
    assert problem_type(response.json()) == "not-found"


async def test_admin_updates_settings_after_verifying_with_their_own_password(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    response = await admin_client.put(SETTINGS, json=settings_update_payload(base_dn=NEW_DN))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == FIELDS
    assert (body["base_dn"], body["revision"], body["updated_by"]) == (NEW_DN, 2, "root")
    assert (await admin_client.get(SETTINGS)).json() == body
    (call,) = use_cases.directory.authenticate_calls
    assert (call.login_id.value, call.password, call.settings.base_dn) == (
        "root",
        "pw-root",
        NEW_DN,
    )


async def test_each_save_bumps_the_revision(admin_client: AsyncClient) -> None:
    first = await admin_client.put(SETTINGS, json=settings_update_payload(1, base_dn="dc=a,dc=t"))
    second = await admin_client.put(SETTINGS, json=settings_update_payload(2, base_dn="dc=b,dc=t"))

    assert (first.json()["revision"], second.json()["revision"]) == (2, 3)


async def test_update_with_the_wrong_password_is_422_and_keeps_the_old_settings(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.put(
        SETTINGS, json=settings_update_payload(password=WRONG_PASSWORD, base_dn=NEW_DN)
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)
    body = response.json()
    assert problem_type(body) == "directory-verification-failed"
    assert body["stage"] == "bind"
    assert WRONG_PASSWORD not in response.text
    kept = (await admin_client.get(SETTINGS)).json()
    assert (kept["revision"], kept["base_dn"]) == (1, "dc=corp,dc=test")


@pytest.mark.parametrize(
    ("error", "stage"),
    [
        (DirectoryUnavailableError(stage=VerificationStage.CONNECT), "connect"),
        (DirectoryUnavailableError(stage=VerificationStage.TLS), "tls"),
        (DirectoryMisconfiguredError(stage=VerificationStage.SEARCH), "search"),
        (InvalidCredentialsError(stage=VerificationStage.BIND), "bind"),
    ],
)
async def test_update_verification_failure_is_422_with_the_failed_stage(
    admin_client: AsyncClient, use_cases: FakeUseCases, error: Exception, stage: str
) -> None:
    use_cases.directory.fail_with = error  # type: ignore[assignment]

    response = await admin_client.put(SETTINGS, json=settings_update_payload(base_dn=NEW_DN))

    assert response.status_code == 422
    assert problem_type(response.json()) == "directory-verification-failed"
    assert response.json()["stage"] == stage
    assert response.json()["detail"]
    assert (await admin_client.get(SETTINGS)).json()["revision"] == 1


async def test_update_with_a_stale_revision_is_409_without_calling_the_directory(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await admin_client.put(SETTINGS, json=settings_update_payload(1, base_dn="dc=a,dc=t"))
    calls = len(use_cases.directory.authenticate_calls)

    response = await admin_client.put(SETTINGS, json=settings_update_payload(1, base_dn=NEW_DN))

    assert response.status_code == 409
    assert problem_type(response.json()) == "invalid-state"
    assert len(use_cases.directory.authenticate_calls) == calls
    assert (await admin_client.get(SETTINGS)).json()["base_dn"] == "dc=a,dc=t"


async def test_update_without_a_password_is_422_invalid_value_and_skips_the_directory(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    response = await admin_client.put(SETTINGS, json=settings_update_payload(password=None))

    assert response.status_code == 422
    assert problem_type(response.json()) == "invalid-value"
    assert use_cases.directory.authenticate_calls == []
    assert use_cases.directory.probe_calls == []


@pytest.mark.parametrize("password", ["", "   ", "pw\x00x", "p" * 257])
async def test_update_with_an_unusable_password_is_422_and_skips_the_directory(
    admin_client: AsyncClient, use_cases: FakeUseCases, password: str
) -> None:
    response = await admin_client.put(
        SETTINGS, json=settings_update_payload(password=password, base_dn=NEW_DN)
    )

    assert response.status_code == 422
    assert use_cases.directory.authenticate_calls == []
    assert (await admin_client.get(SETTINGS)).json()["revision"] == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"server_urls": []},
        {"server_urls": ["ldap://dc1.corp.test"], "use_starttls": False},
        {"server_urls": ["http://dc1.corp.test"]},
        {"bind_template": "no-placeholder"},
        {"connect_timeout_seconds": 0},
        {"receive_timeout_seconds": 61},
        {"ca_cert_pem": "not a pem"},
    ],
)
async def test_update_with_invalid_settings_is_422_and_changes_nothing(
    admin_client: AsyncClient, use_cases: FakeUseCases, overrides: dict[str, Any]
) -> None:
    response = await admin_client.put(SETTINGS, json=settings_update_payload(**overrides))

    assert response.status_code == 422
    assert problem_type(response.json()) in {"invalid-value", "request-validation"}
    assert use_cases.directory.authenticate_calls == []
    assert (await admin_client.get(SETTINGS)).json()["revision"] == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("expected_revision"),
        lambda p: p.update(expected_revision=0),
        lambda p: p.update(expected_revision="1"),
        lambda p: p.update(unknown_field=1),
        lambda p: p.pop("base_dn"),
    ],
)
async def test_update_with_a_malformed_body_is_422_request_validation(
    admin_client: AsyncClient, mutate: object
) -> None:
    payload = settings_update_payload()
    mutate(payload)  # type: ignore[operator]

    response = await admin_client.put(SETTINGS, json=payload)

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"
