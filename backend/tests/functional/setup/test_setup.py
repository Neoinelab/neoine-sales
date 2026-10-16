"""Feature: 처음 설치한 시스템은 3단계(AD 연결, 저장 위치, 최초 admin 지정)로 설정되고 닫힌다."""

from typing import TYPE_CHECKING

import pytest

from tests.factories_auth import WRONG_PASSWORD
from tests.functional.steps.auth import (
    directory_payload,
    given_ad_account,
    given_admin_exists,
    given_logged_out,
)
from tests.functional.steps.common import (
    then_body_includes,
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.login import (
    directory_call_count,
    then_auth_flags_are,
    then_directory_was_not_asked_again,
    then_no_cookie_is_set,
    then_signed_in_as,
)
from tests.functional.steps.session import (
    then_caller_is_anonymous,
    then_me_is,
    then_session_cookie_is_http_only_lax,
)
from tests.functional.steps.setup import (
    SETTINGS_KEYS,
    given_directory_step_done,
    given_setup_completed_by,
    given_storage_step_done,
    probe_count,
    then_directory_must_be_saved_first,
    then_directory_probe_count_is,
    then_setup_is_closed,
    then_user_is_not_registered,
    when_read_auth_config,
    when_save_directory,
    when_set_up_admin,
    when_setup_step_is_requested,
    when_setup_step_is_requested_without_csrf_header,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_fresh_system_needs_the_directory_and_storage_steps(api: Api) -> None:
    """Scenario: 처음 설치한 시스템은 AD 연결과 파일 저장 위치가 필요하고 admin은 그다음이다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_read_auth_config(api)
    # Then
    then_status_is(response, 200)
    await then_auth_flags_are(api, needs_directory=True, needs_storage=True, needs_admin=False)


async def test_saving_the_directory_moves_setup_on_to_the_storage_step(api: Api) -> None:
    """Scenario: 1단계로 AD 연결을 저장하면 다음에는 파일 저장 위치 단계가 남는다(admin은 그 뒤)."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_save_directory(api)
    # Then
    then_status_is(response, 200)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=True, needs_admin=False)


async def test_three_step_setup_signs_in_the_first_admin(api: Api) -> None:
    """Scenario: 3단계에서 AD 계정을 확인하면 그 계정이 최초 admin이 되어 로그인된다."""
    # Given
    given_ad_account(api, login_id="kim", display_name="김관리", email="kim@corp.test")
    await given_storage_step_done(api)
    # When
    response = await when_set_up_admin(api)
    # Then
    then_signed_in_as(response, subject="kim", email="kim@corp.test", name="김관리", role="admin")
    then_session_cookie_is_http_only_lax(response)
    await then_me_is(api, role="admin")
    await then_auth_flags_are(api, needs_directory=False, needs_storage=False, needs_admin=False)
    then_body_includes(await api.get("/api/v1/auth/config"), directory_login=True)


async def test_setup_directory_returns_the_saved_settings_with_revision(api: Api) -> None:
    """Scenario: 1단계 저장 응답은 저장된 설정과 revision 1을 돌려주고 저장자는 비어 있다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_save_directory(api)
    # Then
    body = response.json()
    assert set(body) == SETTINGS_KEYS
    assert (body["revision"], body["updated_by"]) == (1, None)
    assert body["server_urls"] == ["ldaps://dc1.corp.test"]
    assert body["base_dn"] == directory_payload()["base_dn"]


async def test_setup_directory_can_be_overwritten_before_the_first_admin(api: Api) -> None:
    """Scenario: 최초 admin이 생기기 전에는 1단계를 다시 저장해 덮어쓸 수 있다(revision 증가)."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_save_directory(api, base_dn="dc=other,dc=test")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, revision=2, base_dn="dc=other,dc=test")
    then_directory_probe_count_is(api, 2)


async def test_setup_directory_requires_no_session(api: Api) -> None:
    """Scenario: 설정 1단계는 로그인 없이 저장할 수 있다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_save_directory(api)
    # Then
    then_status_is(response, 200)
    await then_caller_is_anonymous(api)


@pytest.mark.parametrize("step", ["directory", "storage", "storage-test", "admin"])
async def test_setup_endpoints_close_after_the_first_admin(api: Api, step: str) -> None:
    """Scenario: 최초 admin이 생긴 뒤에는 모든 설정 단계가 409로 닫히고 AD를 호출하지 않는다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    given_ad_account(api, login_id="kim")
    auth_calls_before, probes_before = directory_call_count(api), probe_count(api)
    # When
    response = await when_setup_step_is_requested(api, step=step)
    # Then
    then_setup_is_closed(response)
    then_directory_was_not_asked_again(api, calls_before=auth_calls_before)
    then_directory_probe_count_is(api, probes_before)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=False, needs_admin=False)


@pytest.mark.parametrize("step", ["directory", "storage", "storage-test", "admin"])
async def test_setup_stays_closed_after_the_setup_admin_is_registered(api: Api, step: str) -> None:
    """Scenario: 설정으로 만든 최초 admin이 있으면 다른 사람이 설정을 다시 열 수 없다."""
    # Given
    await given_setup_completed_by(api, login_id="kim")
    given_ad_account(api, login_id="mallory")
    # When
    response = await when_setup_step_is_requested(api, step=step, login_id="mallory")
    # Then
    then_status_is(response, 409)
    await then_user_is_not_registered(api, login_id="mallory")


async def test_setup_admin_before_directory_is_409_without_asking_the_directory(api: Api) -> None:
    """Scenario: 1단계 전에 최초 admin을 지정하면 409이고 AD를 호출하지 않는다."""
    # Given
    given_ad_account(api, login_id="kim")
    calls_before = directory_call_count(api)
    # When
    response = await when_set_up_admin(api)
    # Then
    then_directory_must_be_saved_first(response)
    then_directory_was_not_asked_again(api, calls_before=calls_before)


@pytest.mark.parametrize("step", ["directory", "storage", "storage-test", "admin"])
async def test_setup_requests_need_the_csrf_header(api: Api, step: str) -> None:
    """Scenario: CSRF 헤더 없는 설정 요청은 403이고 AD를 호출하지 않는다."""
    # Given
    given_ad_account(api, login_id="kim")
    await given_directory_step_done(api)
    calls_before, probes_before = directory_call_count(api), probe_count(api)
    # When
    response = await when_setup_step_is_requested_without_csrf_header(api, step=step)
    # Then
    then_problem_is(response, status=403, type_suffix="csrf")
    then_directory_was_not_asked_again(api, calls_before=calls_before)
    then_directory_probe_count_is(api, probes_before)


async def test_setup_admin_wrong_password_is_the_login_failure(api: Api) -> None:
    """Scenario: 3단계에서 비밀번호가 틀리면 로그인 실패와 같은 401이고 설정은 계속 열려 있다."""
    # Given
    given_ad_account(api, login_id="kim")
    await given_storage_step_done(api)
    # When
    response = await when_set_up_admin(api, password=WRONG_PASSWORD)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
    then_no_cookie_is_set(response)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=False, needs_admin=True)
