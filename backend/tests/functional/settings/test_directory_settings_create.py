"""Feature: AD 설정이 없을 때 admin이 관리 화면에서 새로 등록한다(expected_revision이 null).

설정이 없는 시스템(마이그레이션 직후 admin이 있는 경우)에서 개발 로그인 admin 또는 대체 로그인으로
들어온 admin이 외부연동 화면에서 설정을 만든다. 이미 설정이 있는데 null이면 충돌(409), 설정이 없는데
정수면 404다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.factories_auth import BASE_DN, BIND_PASSWORD
from tests.functional.steps.auth import ADMIN_LOGIN, given_admin_exists, given_logged_out
from tests.functional.steps.common import then_status_is
from tests.functional.steps.fallback import (
    given_directory_settings_are_missing,
    then_signed_in_with_warning,
    when_log_in_with_the_directory_password,
)
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.settings import (
    ADMIN_PASSWORD,
    NEW_BIND_PASSWORD,
    current_user_id,
    directory_error,
    given_dev_login_admin,
    given_directory_discovery_fails_with,
    given_directory_reports_base_dn,
    given_no_directory_calls_yet,
    then_updated_by_is_user_ref,
    update_payload,
    when_read_settings,
    when_update_settings,
)
from tests.functional.steps.setup import then_directory_discover_count_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _dev_admin_without_settings(api: Api) -> None:
    await given_dev_login_admin(api)
    await given_directory_settings_are_missing(api)


async def test_dev_admin_creates_the_settings_with_a_null_revision(api: Api) -> None:
    """Scenario: 개발 로그인 admin이 null revision으로 만들면 revision 1과 Base DN이 저장된다."""
    # Given
    await _dev_admin_without_settings(api)
    given_directory_reports_base_dn(api, "dc=created,dc=test")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(
        api, update_payload(None, None, bind_password=NEW_BIND_PASSWORD)
    )
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert (body["revision"], body["base_dn"]) == (1, "dc=created,dc=test")
    assert body["bind_credential_status"] == "ok"
    then_updated_by_is_user_ref(body, user_id=await current_user_id(api), name="개발 사용자(admin)")
    then_directory_discover_count_is(api, 1)  # 개발 로그인 admin은 Base DN 탐색까지만 확인한다
    assert api.directory.authenticate_calls == []
    assert (await when_read_settings(api)).json() == body


async def test_creating_without_a_bind_password_is_rejected(api: Api) -> None:
    """Scenario: 새로 만들 때 bind_password를 생략하거나 null로 보내면 422(invalid-value)이다."""
    # Given
    await _dev_admin_without_settings(api)
    given_no_directory_calls_yet(api)
    # When
    omitted = await when_update_settings(api, update_payload(None, None))
    nulled = await when_update_settings(api, update_payload(None, None, bind_password=None))
    # Then
    for response in (omitted, nulled):
        then_problem_kind_is(response, status=422, kinds=("invalid-value",))
        assert "bind_password" in response.text
    assert api.directory.discover_calls == []
    assert (await when_read_settings(api)).status_code == 404


async def test_creating_when_settings_already_exist_is_409(api: Api) -> None:
    """Scenario: 설정이 이미 있는데 expected_revision이 null이면 409(invalid-state)이다."""
    # Given
    await given_dev_login_admin(api)  # 최초 설정 1단계가 끝나 설정이 있다
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(
        api, update_payload(None, None, bind_password=NEW_BIND_PASSWORD)
    )
    # Then
    then_problem_kind_is(response, status=409, kinds=("invalid-state",))
    assert api.directory.discover_calls == []
    assert (await when_read_settings(api)).json()["revision"] == 1


async def test_an_integer_revision_without_settings_is_404(api: Api) -> None:
    """Scenario: 설정이 없는데 정수 revision으로 저장하면 404(not-found)이다."""
    # Given
    await _dev_admin_without_settings(api)
    # When
    response = await when_update_settings(
        api, update_payload(1, None, bind_password=NEW_BIND_PASSWORD)
    )
    # Then
    then_problem_kind_is(response, status=404, kinds=("not-found",))


async def test_creation_failure_stores_nothing(api: Api) -> None:
    """Scenario: 새로 만들 때 서비스 계정 확인이 실패하면 422이고 설정은 만들어지지 않는다."""
    # Given
    await _dev_admin_without_settings(api)
    given_directory_discovery_fails_with(api, directory_error("misconfigured", "service_bind"))
    # When
    response = await when_update_settings(
        api, update_payload(None, None, bind_password=NEW_BIND_PASSWORD)
    )
    # Then
    then_problem_kind_is(response, status=422, kinds=("directory-verification-failed",))
    assert response.json()["stage"] == "service_bind"
    assert (await when_read_settings(api)).status_code == 404


async def test_a_fallback_login_admin_creates_the_settings_after_confirming_the_password(
    api: Api,
) -> None:
    """Scenario: 설정이 없어 대체 로그인으로 들어온 admin이 admin 비밀번호 확인 뒤 설정을 만든다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    await given_directory_settings_are_missing(api)
    login = await when_log_in_with_the_directory_password(api, login_id=ADMIN_LOGIN)
    then_signed_in_with_warning(login, stage="not_configured")
    given_directory_reports_base_dn(api, BASE_DN)
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(
        api, update_payload(None, ADMIN_PASSWORD, bind_password=BIND_PASSWORD)
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["revision"] == 1
    (call,) = api.directory.authenticate_calls
    assert (call.login_id.value, call.password, call.base_dn) == (
        ADMIN_LOGIN,
        ADMIN_PASSWORD,
        BASE_DN,
    )
    assert BIND_PASSWORD not in response.text
