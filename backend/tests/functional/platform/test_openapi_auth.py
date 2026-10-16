"""Feature: 인증 API는 공개된 계약대로의 경로·설정 플래그만 갖고 응답에 비밀번호가 없다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.openapi_checks import (
    then_login_and_setup_passwords_are_masked_secrets,
    then_no_response_schema_has_a_password_field,
)
from tests.functional.steps.platform import spec_of, when_fetch_openapi

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_auth_routes_have_the_new_methods_and_no_oidc_routes(api: Api) -> None:
    """Scenario: 인증 경로는 계획된 메서드만 공개하고 OIDC 콜백 경로는 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    paths = spec_of(response)["paths"]
    assert set(paths["/api/v1/auth/login"]) == {"post"}
    assert set(paths["/api/v1/auth/setup"]) == {"post"}
    assert set(paths["/api/v1/auth/setup/directory"]) == {"put"}
    assert set(paths["/api/v1/auth/setup/storage"]) == {"put"}
    assert set(paths["/api/v1/auth/setup/storage/test"]) == {"post"}
    assert set(paths["/api/v1/settings/storage"]) == {"get", "put"}
    assert set(paths["/api/v1/settings/storage/test"]) == {"post"}
    assert "/api/v1/auth/callback" not in paths


async def test_auth_config_schema_has_exactly_the_five_flags(api: Api) -> None:
    """Scenario: 로그인 화면 설정 응답은 정확히 다섯 개의 플래그를 가진다(저장 위치 단계 포함)."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    schema = spec_of(response)["components"]["schemas"]["AuthConfigResponse"]
    assert set(schema["properties"]) == {
        "dev_login",
        "directory_login",
        "needs_directory_setup",
        "needs_storage_setup",
        "needs_admin_setup",
    }
    assert set(schema["required"]) >= {"needs_storage_setup"}


async def test_no_response_schema_contains_a_password_field(api: Api) -> None:
    """Scenario: 어떤 응답 스키마(중첩 포함)에도 비밀번호 필드가 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_no_response_schema_has_a_password_field(response)


async def test_password_request_fields_are_masked_secrets(api: Api) -> None:
    """Scenario: 로그인·최초 설정 요청의 password는 마스킹되는 쓰기 전용 비밀 값이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_fetch_openapi(api)
    # Then
    then_login_and_setup_passwords_are_masked_secrets(response)
