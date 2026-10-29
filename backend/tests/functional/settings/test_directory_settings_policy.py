"""Feature: AD 설정 저장에는 시도 제한·CSRF·개발 로그인 규칙이 적용되고 저장은 안전하게 반영된다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import (
    ADMIN_LOGIN,
    ME,
    given_logged_in_as,
    given_user_registered,
    password_of,
)
from tests.functional.steps.common import then_status_is
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.rereads import (
    then_session_still_works,
    then_settings_can_be_read,
    then_settings_equal,
)
from tests.functional.steps.session import when_get_with_session
from tests.functional.steps.settings import (
    NEW_DN,
    SETTINGS,
    current_user_id,
    directory_error,
    given_dev_login_admin,
    given_directory_discovery_fails_with,
    given_directory_reports_base_dn,
    given_no_directory_calls_yet,
    given_session_token,
    given_wrong_password_attempts,
    then_config_offers_directory_login,
    then_directory_authenticated_once,
    then_directory_not_called,
    then_stored_settings_are,
    then_updated_by_is_user_ref,
    update_payload,
    when_log_in,
    when_update_settings,
    when_update_settings_without_csrf_header,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_update_attempts_are_limited_per_admin_account(api: Api) -> None:
    """Scenario: 실패 제한 횟수를 채운 admin 계정의 다음 저장은 429이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_wrong_password_attempts(api, endpoint=SETTINGS)
    given_no_directory_calls_yet(api)
    # When
    given_directory_reports_base_dn(api, NEW_DN)
    response = await when_update_settings(api, update_payload(connect_timeout_seconds=9))
    # Then
    then_problem_kind_is(response, status=429, kinds=("too-many-attempts",))
    then_directory_not_called(api)


async def test_update_requires_the_csrf_header(api: Api) -> None:
    """Scenario: CSRF 헤더 없이 저장하면 403(csrf)이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_settings_without_csrf_header(api)
    # Then
    then_problem_kind_is(response, status=403, kinds=("csrf",))
    await then_stored_settings_are(api, revision=1, base_dn="dc=corp,dc=test")


async def test_a_dev_login_admin_saves_after_discovering_the_base_dn_only(api: Api) -> None:
    """Scenario: 개발 로그인 admin은 admin 비밀번호 없이 저장하고 AD에는 Base DN 탐색까지만 한다."""
    # Given
    await given_dev_login_admin(api)
    given_directory_reports_base_dn(api, NEW_DN)
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(
        api, update_payload(password=None, connect_timeout_seconds=9)
    )
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert (body["revision"], body["base_dn"]) == (2, NEW_DN)
    then_updated_by_is_user_ref(body, user_id=await current_user_id(api), name="개발 사용자(admin)")
    assert "login_id" not in body["updated_by"]
    assert len(api.directory.discover_calls) == 1
    assert api.directory.authenticate_calls == []


async def test_a_dev_login_admin_update_fails_422_when_the_discovery_fails(api: Api) -> None:
    """Scenario: 개발 로그인 admin의 Base DN 탐색이 실패하면 422이고 실패한 단계를 알려 준다."""
    # Given
    await given_dev_login_admin(api)
    given_directory_discovery_fails_with(api, directory_error("unavailable", "connect"))
    # When
    response = await when_update_settings(api, update_payload(password=None))
    # Then
    then_status_is(response, 422)
    assert response.json()["stage"] == "connect"


async def test_changing_settings_keeps_every_existing_session(api: Api) -> None:
    """Scenario: 설정을 저장해도 이미 열린 다른 사용자의 세션은 그대로 유효하다."""
    # Given
    await given_user_registered(api, login_id="kim", role="sales")
    kim_token = await given_session_token(api, login_id="kim")
    await given_logged_in_as(api, role="admin")
    # When
    given_directory_reports_base_dn(api, NEW_DN)
    saved = await when_update_settings(api, update_payload(connect_timeout_seconds=9))
    # Then
    then_status_is(saved, 200)
    await then_session_still_works(api, ME, token=kim_token, role="sales")
    await then_settings_can_be_read(api)


async def test_a_saved_update_is_attributed_to_the_admin_and_visible_to_everyone(api: Api) -> None:
    """Scenario: 저장 결과는 저장한 admin 이름으로 남고 GET과 같으며 로그인 화면 설정에 반영된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_directory_reports_base_dn(api, NEW_DN)
    # When
    saved = await when_update_settings(api, update_payload(connect_timeout_seconds=9))
    # Then
    then_status_is(saved, 200)
    assert saved.json()["revision"] == 2
    then_updated_by_is_user_ref(saved.json(), user_id=await current_user_id(api), name="관리자")
    assert "login_id" not in saved.json()["updated_by"]
    await then_settings_equal(api, saved.json())
    await then_config_offers_directory_login(api)


async def test_new_settings_apply_to_the_next_login(api: Api) -> None:
    """Scenario: 저장해 둔 Base DN과 비밀번호가 다음 로그인의 AD 인증에 쓰인다(다시 찾지 않는다)."""
    # Given
    await given_user_registered(api, login_id="kim", role="sales")
    given_directory_reports_base_dn(api, NEW_DN)
    saved = await when_update_settings(api, update_payload(connect_timeout_seconds=9))
    then_status_is(saved, 200)
    api.forget_session()
    given_no_directory_calls_yet(api)
    # When
    login = await when_log_in(api, "kim")
    # Then
    then_status_is(login, 200)
    then_directory_authenticated_once(
        api, login_id="kim", password=password_of("kim"), base_dn=NEW_DN
    )
    assert api.directory.discover_calls == []  # 로그인마다 Base DN을 다시 찾지 않는다


async def test_settings_are_read_from_the_database_by_every_app_instance(api: Api) -> None:
    """Scenario: 다른 서버 인스턴스도 같은 세션으로 방금 저장된 설정을 읽는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    token = await given_session_token(api, login_id=ADMIN_LOGIN)
    given_directory_reports_base_dn(api, NEW_DN)
    await when_update_settings(api, update_payload(connect_timeout_seconds=9))
    await api.reopen()  # 같은 DB를 보는 새 앱 인스턴스(다른 워커·서버)
    # When
    response = await when_get_with_session(api, SETTINGS, token=token)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert (body["base_dn"], body["revision"]) == (NEW_DN, 2)
