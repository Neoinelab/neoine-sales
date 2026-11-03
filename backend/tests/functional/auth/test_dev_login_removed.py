"""Feature: 개발용 로그인은 없다. 예약된 개발용 세 아이디로는 로그인할 수 없다."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from tests.functional.steps.auth import (
    CONFIG,
    given_ad_account,
    given_admin_exists,
    given_logged_out,
    given_user_registered,
    password_of,
)
from tests.functional.steps.common import then_status_is
from tests.functional.steps.login import when_log_in
from tests.functional.steps.platform import spec_of, when_fetch_openapi
from tests.functional.steps.requests import when_get
from tests.functional.steps.session import SESSION_COOKIE
from tests.functional.steps.settings import given_no_directory_calls_yet

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

DEV_LOGIN = "/api/v1/auth/dev-login"
CONFIG_KEYS = {
    "directory_login",
    "needs_directory_setup",
    "needs_storage_setup",
    "needs_admin_setup",
    "auth_mode",
}


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_the_dev_login_endpoint_does_not_exist(api: Api, role: str) -> None:
    """Scenario: 어느 환경에서도 POST /auth/dev-login은 없고 세션 쿠키도 만들어지지 않는다."""
    # Given
    # (아무 설정 없는 새 시스템)
    # When
    response = await api.post(DEV_LOGIN, json={"role": role})
    # Then
    then_status_is(response, 404)
    assert SESSION_COOKIE not in response.cookies


async def test_the_openapi_has_no_dev_login_path_or_schema(api: Api) -> None:
    """Scenario: 공개된 API 계약에 개발용 로그인 경로와 요청 스키마가 없다."""
    # Given
    # (아무 설정 없는 새 시스템)
    # When
    response = await when_fetch_openapi(api)
    # Then
    spec = spec_of(response)
    assert DEV_LOGIN not in spec["paths"]
    assert "DevLoginRequest" not in spec["components"]["schemas"]


async def test_auth_config_no_longer_reports_dev_login(api: Api) -> None:
    """Scenario: 인증 설정 응답은 다섯 개 키뿐이고 dev_login이 없다."""
    # Given
    # (아무 설정 없는 새 시스템)
    # When
    response = await when_get(api, CONFIG)
    # Then
    then_status_is(response, 200)
    assert set(response.json()) == CONFIG_KEYS


@pytest.mark.parametrize("login_id", ["dev-admin", "dev-sales", "dev-user", "DEV-Admin"])
async def test_a_retired_dev_login_id_cannot_sign_in(api: Api, login_id: str) -> None:
    """Scenario: 예약 세 아이디는 AD에 계정이 있어도 401이고 AD를 부르지 않는다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    given_ad_account(api, login_id=login_id)
    given_no_directory_calls_yet(api)
    # When
    response = await when_log_in(api, login_id=login_id, password=password_of(login_id))
    # Then
    then_status_is(response, 401)
    assert response.json()["detail"] == LOGIN_FAILED
    assert SESSION_COOKIE not in response.cookies
    assert api.directory.authenticate_calls == []
    assert api.directory.discover_calls == []


@pytest.mark.parametrize("login_id", ["dev-qa", "dev-admin2", "dev-ops"])
async def test_another_dev_prefixed_id_signs_in_through_the_normal_flow(
    api: Api, login_id: str
) -> None:
    """Scenario: 예약 세 아이디가 아닌 dev- 아이디는 등록된 일반 사용자로 로그인된다."""
    # Given
    await given_admin_exists(api)
    await given_user_registered(api, login_id=login_id, role="sales")
    await given_logged_out(api)
    given_ad_account(api, login_id=login_id)
    # When
    response = await when_log_in(api, login_id=login_id, password=password_of(login_id))
    # Then
    then_status_is(response, 200)
    assert SESSION_COOKIE in response.cookies
    assert len(api.directory.authenticate_calls) == 1
