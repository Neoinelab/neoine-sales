"""최초 설정 API의 검증·실패 경로 (DS-2~5, SETUP-3·8, AUTH-4·5·7, T-E15·E16)."""

import json
from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import (
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from tests.e2e.payloads_auth import (
    SETUP,
    SETUP_DIRECTORY,
    credentials,
    directory_payload,
    problem_type,
)
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.auth_seed import DUMMY_PASSWORD

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

LEAK = "internal-ldap-server-banner"
PROBLEM = "application/problem+json"
CONFIG_FLAGS = "/api/v1/auth/config"


async def _flags(client: AsyncClient) -> tuple[bool, bool]:
    body = (await client.get(CONFIG_FLAGS)).json()
    return body["needs_directory_setup"], body["needs_admin_setup"]


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"server_urls": ["http://dc1.corp.test"]}, "server_urls"),
        ({"server_urls": ["ldaps://dc1.corp.test/path"]}, "server_urls"),
        ({"server_urls": ["ldaps://dc1.corp.test:70000"]}, "server_urls"),
        ({"server_urls": ["ldaps://dc1.corp.test", "ldaps://dc1.corp.test:636"]}, "server_urls"),
        ({"server_urls": []}, "server_urls"),
        ({"server_urls": [f"ldaps://dc{n}.corp.test" for n in range(6)]}, "server_urls"),
        ({"server_urls": ["ldap://dc1.corp.test"], "use_starttls": False}, "use_starttls"),
        ({"bind_template": "cn=fixed,dc=corp"}, "bind_template"),
        ({"bind_template": "cn={login_id},cn={login_id}"}, "bind_template"),
        ({"user_filter": "sAMAccountName={login_id}"}, "user_filter"),
        ({"base_dn": ""}, "base_dn"),
        ({"display_name_attribute": "1bad"}, "display_name_attribute"),
        ({"email_attribute": "ma il"}, "email_attribute"),
        ({"ca_cert_pem": "not a pem"}, "ca_cert_pem"),
        ({"connect_timeout_seconds": 0}, "connect_timeout_seconds"),
        ({"connect_timeout_seconds": 31}, "connect_timeout_seconds"),
        ({"receive_timeout_seconds": 61}, "receive_timeout_seconds"),
    ],
)
async def test_setup_directory_validation_errors_are_422_naming_the_field(
    anonymous_client: AsyncClient, use_cases: FakeUseCases, override: dict[str, object], field: str
) -> None:
    response = await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload(**override))

    body = response.json()
    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)
    assert problem_type(body) in {"invalid-value", "request-validation"}
    assert field in json.dumps(body, ensure_ascii=False)
    assert use_cases.directory.probe_calls == []
    assert (await _flags(anonymous_client)) == (True, False)


async def test_setup_directory_rejects_unknown_fields(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.put(
        SETUP_DIRECTORY, json={**directory_payload(), "bind_password": "x"}
    )

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"


@pytest.mark.parametrize(
    "stage", [VerificationStage.CONNECT, VerificationStage.TLS], ids=["connect", "tls"]
)
async def test_setup_directory_probe_failure_is_422_with_only_the_coarse_stage(
    anonymous_client: AsyncClient, use_cases: FakeUseCases, stage: VerificationStage
) -> None:
    use_cases.directory.probe_fails_with = DirectoryUnavailableError(LEAK, stage=stage)

    response = await anonymous_client.put(SETUP_DIRECTORY, json=directory_payload())

    body = response.json()
    assert response.status_code == 422
    assert problem_type(body) == "directory-verification-failed"
    assert body["stage"] == stage.value
    assert LEAK not in response.text
    assert await _flags(anonymous_client) == (True, False)  # 아무것도 저장되지 않았다


@pytest.mark.parametrize("password", ["", "   ", "pw\u0000x"])
async def test_setup_admin_empty_password_never_reaches_the_directory(
    anonymous_client: AsyncClient, use_cases: FakeUseCases, password: str
) -> None:
    await use_cases.seed_directory()

    response = await anonymous_client.post(SETUP, json=credentials("kim", password))

    assert response.status_code == 401
    assert use_cases.directory.authenticate_calls == []


async def test_setup_admin_directory_outage_is_503(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_directory()
    use_cases.directory.fail_with = DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS)

    response = await anonymous_client.post(SETUP, json=credentials())

    assert response.status_code == 503
    assert problem_type(response.json()) == "directory-unavailable"
    assert LEAK not in response.text


async def test_setup_admin_is_throttled_with_429(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_directory()
    use_cases.directory.fail_with = InvalidCredentialsError(stage=VerificationStage.BIND)
    for _ in range(MAX_PER_ACCOUNT):
        await anonymous_client.post(SETUP, json=credentials("kim", "wrong"))
    use_cases.directory.fail_with = None
    use_cases.directory.add_account("kim", "pw-kim")
    calls_before = len(use_cases.directory.authenticate_calls)

    response = await anonymous_client.post(SETUP, json=credentials())

    assert response.status_code == 429
    assert problem_type(response.json()) == "too-many-attempts"
    assert len(use_cases.directory.authenticate_calls) == calls_before


async def test_setup_never_echoes_or_logs_the_password(
    anonymous_client: AsyncClient,
    use_cases: FakeUseCases,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG")
    use_cases.directory.add_account("kim", DUMMY_PASSWORD)
    await use_cases.seed_directory()
    responses = [
        await anonymous_client.post(SETUP, json=credentials("kim", DUMMY_PASSWORD + "x")),
        await anonymous_client.post(SETUP, json=credentials("kim", DUMMY_PASSWORD * 20)),
        await anonymous_client.post(SETUP, json=credentials("kim", DUMMY_PASSWORD)),
    ]

    assert [r.status_code for r in responses] == [401, 422, 200]
    for response in responses:
        assert DUMMY_PASSWORD not in response.text
    assert DUMMY_PASSWORD not in caplog.text
