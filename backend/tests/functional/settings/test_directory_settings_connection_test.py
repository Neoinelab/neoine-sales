"""Feature: admin은 AD 연결 설정을 저장하기 전에 연결 테스트로 단계별 결과를 확인할 수 있다."""

from typing import TYPE_CHECKING, Any

import pytest

from tests.factories_auth import BIND_PASSWORD
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.rereads import (
    given_current_settings,
    then_settings_are_unsaved_defaults,
    then_settings_equal,
)
from tests.functional.steps.settings import (
    ADMIN_PASSWORD,
    NEW_BIND_PASSWORD,
    NEW_DN,
    SETTINGS_TEST,
    STORED_DN,
    WRONG_PASSWORD,
    directory_error,
    given_dev_login_admin,
    given_directory_discovery_fails_with,
    given_directory_fails_with,
    given_directory_reports_base_dn,
    given_no_directory_calls_yet,
    given_wrong_password_attempts,
    probe_payload,
    then_directory_authenticated_once,
    then_directory_not_called,
    then_directory_used_bind_password,
    then_stored_settings_are,
    when_test_connection,
    when_test_connection_without_csrf_header,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_successful_test_returns_base_dn(api: Api) -> None:
    """Scenario: 연결 테스트가 성공하면 찾은 Base DN을 담은 결과를 돌려주고 저장은 하지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_directory_reports_base_dn(api, NEW_DN)
    given_no_directory_calls_yet(api)
    # When
    response = await when_test_connection(api, probe_payload(connect_timeout_seconds=9))
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == {"success", "stage", "message", "base_dn"}
    assert (body["success"], body["stage"], body["base_dn"]) == (True, None, NEW_DN)
    assert body["message"]
    then_directory_authenticated_once(api, login_id="root", password=ADMIN_PASSWORD, base_dn=NEW_DN)
    await then_settings_are_unsaved_defaults(api, base_dn=STORED_DN)


async def test_test_endpoint_leaves_the_stored_row_untouched(api: Api) -> None:
    """Scenario: 연결 테스트를 해도 저장된 설정 전체가 테스트 전과 똑같다."""
    # Given
    await given_logged_in_as(api, role="admin")
    before = await given_current_settings(api)
    given_directory_reports_base_dn(api, NEW_DN)
    # When
    response = await when_test_connection(api, probe_payload(connect_timeout_seconds=9))
    # Then
    assert response.json()["success"] is True
    await then_settings_equal(api, before)


async def test_test_endpoint_reports_a_wrong_password_as_a_failed_result_not_an_error(
    api: Api,
) -> None:
    """Scenario: 틀린 비밀번호는 오류가 아니라 bind 단계 실패 결과(200)로 알려 주고 값은 숨긴다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_test_connection(api, probe_payload(password=WRONG_PASSWORD))
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert (body["success"], body["stage"], body["base_dn"]) == (False, "bind", None)
    assert body["message"]
    assert WRONG_PASSWORD not in response.text


@pytest.mark.parametrize(
    ("discovery", "kind", "stage"),
    [
        (True, "unavailable", "connect"),
        (True, "unavailable", "tls"),
        (True, "misconfigured", "service_bind"),
        (True, "misconfigured", "base_dn"),
        (False, "misconfigured", "search"),
        (False, "invalid", "search"),
        (False, "invalid", "bind"),
    ],
)
async def test_failed_stage_is_reported(api: Api, discovery: bool, kind: str, stage: str) -> None:
    """Scenario: 어느 단계에서 실패해도(연결·TLS·서비스 계정·Base DN·검색·bind) 그 단계를 알린다."""
    # Given
    await given_logged_in_as(api, role="admin")
    error = directory_error(kind, stage)
    if discovery:
        given_directory_discovery_fails_with(api, error)
    else:
        given_directory_fails_with(api, error)
    # When
    response = await when_test_connection(api, probe_payload())
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert (body["success"], body["stage"], body["base_dn"]) == (False, stage, None)
    assert body["message"]


async def test_test_endpoint_without_bind_password_uses_the_stored_one(api: Api) -> None:
    """Scenario: bind_password를 생략하면 저장된 비밀번호로 서비스 계정에 접속한다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_test_connection(api, probe_payload(user_filter="(uid={login_id})"))
    # Then
    then_status_is(response, 200)
    assert response.json()["success"] is True
    then_directory_used_bind_password(api, BIND_PASSWORD)


async def test_test_endpoint_with_a_new_bind_password_uses_it_without_saving(api: Api) -> None:
    """Scenario: 새 바인드 비밀번호로 테스트해도 저장하지 않고 응답에 값이 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_test_connection(
        api, probe_payload(host="dc2.corp.test", bind_password=NEW_BIND_PASSWORD)
    )
    # Then
    then_status_is(response, 200)
    then_directory_used_bind_password(api, NEW_BIND_PASSWORD)
    assert NEW_BIND_PASSWORD not in response.text
    await then_stored_settings_are(api, revision=1, base_dn=STORED_DN)


async def test_changing_the_host_without_bind_password_is_rejected(api: Api) -> None:
    """Scenario: 호스트를 바꾸면서 바인드 비밀번호를 생략하면 422이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_test_connection(api, probe_payload(host="dc2.corp.test"))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    assert "bind_password" in response.text
    then_directory_not_called(api)


async def test_test_endpoint_without_a_password_is_422(api: Api) -> None:
    """Scenario: 비밀번호 없이 연결 테스트를 하면 422(invalid-value)이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_test_connection(api, probe_payload(password=None))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    assert api.directory.authenticate_calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"host": ""},
        {"host": "ldaps://dc1.corp.test"},
        {"port": 0},
        {"security": "tls"},
        {"bind_account": ""},
        {"bind_password": ""},
        {"connect_timeout_seconds": 0},
        {"base_dn": "dc=x"},
        {"server_urls": ["ldaps://dc1.corp.test"]},
        {"unknown": 1},
    ],
)
async def test_test_endpoint_rejects_invalid_settings_with_422(
    api: Api, overrides: dict[str, Any]
) -> None:
    """Scenario: 형식이 틀린 연결 설정으로 테스트하면 422이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_test_connection(api, probe_payload(**overrides))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value", "request-validation"))
    then_directory_not_called(api)


async def test_test_endpoint_attempts_are_limited_per_admin_account(api: Api) -> None:
    """Scenario: 실패 제한 횟수를 채운 admin 계정의 다음 연결 테스트는 429이고 AD를 안 부른다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_wrong_password_attempts(api, endpoint=SETTINGS_TEST)
    given_no_directory_calls_yet(api)
    # When
    response = await when_test_connection(api, probe_payload())
    # Then
    then_problem_kind_is(response, status=429, kinds=("too-many-attempts",))
    assert api.directory.authenticate_calls == []


async def test_a_dev_login_admin_test_only_discovers_the_base_dn(api: Api) -> None:
    """Scenario: 개발 로그인 admin의 연결 테스트는 비밀번호 없이 Base DN 탐색까지만 한다."""
    # Given
    await given_dev_login_admin(api)
    given_directory_reports_base_dn(api, NEW_DN)
    given_no_directory_calls_yet(api)
    # When
    response = await when_test_connection(api, probe_payload(password=None))
    # Then
    then_status_is(response, 200)
    assert response.json()["success"] is True
    assert response.json()["base_dn"] == NEW_DN
    assert len(api.directory.discover_calls) == 1
    assert api.directory.authenticate_calls == []


async def test_test_endpoint_requires_the_csrf_header(api: Api) -> None:
    """Scenario: CSRF 헤더 없이 연결 테스트를 하면 403(csrf)이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_test_connection_without_csrf_header(api)
    # Then
    then_problem_kind_is(response, status=403, kinds=("csrf",))
    await then_stored_settings_are(api, revision=1, base_dn=STORED_DN)
