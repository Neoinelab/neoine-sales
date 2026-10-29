"""Feature: 저장된 바인드 비밀번호를 풀 수 없으면(키 변경·분실) 알리고 다시 입력으로 복구한다.

풀 수 없는 상태는 AD가 답할 수 없는 경우처럼 대체 로그인으로 들어간다(stage credential_unreadable).
설정 조회는 성공하되 상태만 unreadable로 알리고, 비밀번호를 생략한 저장·테스트는 거절하며, 새 바인드
비밀번호를 넣으면 정상 저장된다. 최초 admin 등록은 대체 로그인 없이 503이다.
"""

import logging
from typing import TYPE_CHECKING

import pytest

from tests.factories_auth import BIND_PASSWORD
from tests.functional.steps.auth import (
    ADMIN_LOGIN,
    given_ad_account,
    given_admin_exists,
    given_logged_out,
)
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.fallback import (
    given_bind_password_sealed_with_another_key,
    then_signed_in_with_warning,
    then_signed_in_without_warning,
    when_log_in_with_the_directory_password,
)
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.settings import (
    NEW_BIND_PASSWORD,
    given_no_directory_calls_yet,
    probe_payload,
    update_payload,
    when_read_settings,
    when_test_connection,
    when_update_settings,
)
from tests.functional.steps.setup import (
    given_storage_step_done,
    then_user_is_not_registered,
    when_set_up_admin,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
KEY_HINT = "AD 바인드 비밀번호를 복호화하지 못했습니다(암호화 키 변경 여부 확인)"


async def _admin_signed_in_with_unreadable_credential(api: Api) -> None:
    """admin(root)이 해시로 대체 로그인해 들어와 있고, 바인드 비밀번호는 풀 수 없는 상태다."""
    await given_admin_exists(api)
    await given_logged_out(api)
    await given_bind_password_sealed_with_another_key(api)
    response = await when_log_in_with_the_directory_password(api, login_id=ADMIN_LOGIN)
    then_signed_in_with_warning(response, stage="credential_unreadable")


async def test_admin_with_a_stored_hash_signs_in_with_the_credential_unreadable_warning(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: 비밀번호를 풀 수 없으면 해시가 있는 admin은 들어오고 안내 로그와 경고를 받는다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    await given_bind_password_sealed_with_another_key(api)
    caplog.set_level(logging.DEBUG)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id=ADMIN_LOGIN)
    # Then
    then_signed_in_with_warning(response, stage="credential_unreadable")
    assert KEY_HINT in caplog.text
    assert BIND_PASSWORD not in caplog.text


async def test_reading_the_settings_reports_the_unreadable_credential(api: Api) -> None:
    """Scenario: 설정 조회는 200이고 bind_credential_status가 unreadable이다(값은 없다)."""
    # Given
    await _admin_signed_in_with_unreadable_credential(api)
    # When
    response = await when_read_settings(api)
    # Then
    then_status_is(response, 200)
    assert response.json()["bind_credential_status"] == "unreadable"
    assert BIND_PASSWORD not in response.text


async def test_saving_without_a_bind_password_is_rejected_with_a_retype_hint(api: Api) -> None:
    """Scenario: 비밀번호를 생략한 저장은 422(invalid-value)이고 다시 입력하라고 안내한다."""
    # Given
    await _admin_signed_in_with_unreadable_credential(api)
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(connect_timeout_seconds=9))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    assert "bind_password" in response.text
    assert api.directory.authenticate_calls == []


async def test_testing_without_a_bind_password_is_rejected_too(api: Api) -> None:
    """Scenario: 비밀번호를 생략한 연결 테스트도 422(invalid-value)이다."""
    # Given
    await _admin_signed_in_with_unreadable_credential(api)
    # When
    response = await when_test_connection(api, probe_payload())
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    assert "bind_password" in response.text


async def test_saving_a_new_bind_password_recovers_and_directory_login_works_again(
    api: Api,
) -> None:
    """Scenario: 새 바인드 비밀번호로 저장하면 정상 저장되고 다음 로그인은 경고 없이 AD를 거친다."""
    # Given
    await _admin_signed_in_with_unreadable_credential(api)
    # When
    saved = await when_update_settings(api, update_payload(bind_password=NEW_BIND_PASSWORD))
    # Then
    then_status_is(saved, 200)
    assert saved.json()["bind_credential_status"] == "ok"
    assert (await when_read_settings(api)).json()["bind_credential_status"] == "ok"
    await given_logged_out(api)
    login = await when_log_in_with_the_directory_password(api, login_id=ADMIN_LOGIN)
    then_signed_in_without_warning(login)


async def test_first_admin_setup_with_an_unreadable_credential_is_503(api: Api) -> None:
    """Scenario: 최초 admin 등록은 대체 로그인 없이 503(directory-unavailable)이고 등록 안 된다."""
    # Given
    given_ad_account(api, login_id="kim")
    await given_storage_step_done(api)
    await given_bind_password_sealed_with_another_key(api)
    # When
    response = await when_set_up_admin(api, login_id="kim")
    # Then
    then_problem_is(response, status=503, type_suffix="directory-unavailable")
    await then_user_is_not_registered(api, login_id="kim")
