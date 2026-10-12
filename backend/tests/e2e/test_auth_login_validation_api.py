"""POST /api/v1/auth/login의 입력 검증·누출 방지·OIDC 경로 제거 (AUTH-4·7·8·9, T-E6·E10)."""

import json
from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from tests.e2e.payloads_auth import CONFIG, LOGIN, credentials, problem_type
from tests.support.auth_seed import DUMMY_PASSWORD

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "body",
    [{}, {"login_id": "kim"}, {"password": "x"}, {**credentials(), "role": "admin"}],
    ids=["empty", "no-password", "no-login-id", "extra-field"],
)
async def test_malformed_login_bodies_are_422(
    anonymous_client: AsyncClient, body: dict[str, str]
) -> None:
    response = await anonymous_client.post(LOGIN, json=body)

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"


@pytest.mark.usefixtures("ready")
async def test_oversized_inputs_are_422_without_echoing_the_value(
    anonymous_client: AsyncClient,
) -> None:
    long_password = DUMMY_PASSWORD + "p" * 300
    too_long_id = "i" * 300

    by_password = await anonymous_client.post(LOGIN, json=credentials("kim", long_password))
    by_login_id = await anonymous_client.post(LOGIN, json=credentials(too_long_id, "pw"))

    assert by_password.status_code == by_login_id.status_code == 422
    assert long_password not in by_password.text
    assert DUMMY_PASSWORD not in by_password.text
    assert "input" not in json.dumps(by_password.json()["errors"])


@pytest.mark.usefixtures("ready")
async def test_legacy_oidc_routes_do_not_exist(anonymous_client: AsyncClient) -> None:
    login = await anonymous_client.get(LOGIN)
    callback = await anonymous_client.get("/api/v1/auth/callback", params={"code": "c"})

    assert login.status_code in (404, 405)
    assert callback.status_code == 404
    assert "location" not in login.headers
    assert "location" not in callback.headers


@pytest.mark.usefixtures("ready")
async def test_password_never_appears_in_responses_or_logs(
    anonymous_client: AsyncClient,
    ready: FakeUseCases,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG")
    ready.directory.add_account("kim", DUMMY_PASSWORD)
    responses = [
        await anonymous_client.post(LOGIN, json=credentials("kim", DUMMY_PASSWORD)),
        await anonymous_client.post(LOGIN, json=credentials("kim", DUMMY_PASSWORD + "x")),
        await anonymous_client.post(LOGIN, json=credentials("kim", DUMMY_PASSWORD * 20)),
    ]
    ready.directory.fail_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)
    responses.append(await anonymous_client.post(LOGIN, json=credentials("kim", DUMMY_PASSWORD)))

    assert [r.status_code for r in responses] == [200, 401, 422, 503]
    for response in responses:
        assert DUMMY_PASSWORD not in response.text
        assert DUMMY_PASSWORD not in str(response.headers)
    assert DUMMY_PASSWORD not in caplog.text


async def test_auth_config_has_exactly_the_four_flags(anonymous_client: AsyncClient) -> None:
    body = (await anonymous_client.get(CONFIG)).json()

    assert set(body) == {
        "dev_login",
        "directory_login",
        "needs_directory_setup",
        "needs_admin_setup",
    }
    assert "oidc" not in body
