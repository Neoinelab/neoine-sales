"""Feature: 처음 설치한 시스템은 AD 없이 앱에서 계정을 직접 관리하도록 3단계로 설정한다.

1단계에서 인증 방식(ad|local)을 고르고, local이면 AD 연결 없이 저장 위치 → 첫 admin(아이디·비밀번호·
이름·이메일·전화) 등록으로 진행한다. admin이 생기면 모든 단계가 닫힌다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import AUTH_MODE_FIRST, SETUP_CLOSED
from tests.functional.steps.auth import (
    SETUP_STORAGE,
    given_ad_account,
    given_admin_exists,
    given_logged_out,
    storage_path_of,
)
from tests.functional.steps.common import (
    then_body_includes,
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.local_accounts import (
    given_auth_mode_chosen,
    given_local_storage_step_done,
    local_password_of,
    then_auth_config_is,
    then_no_user_registered,
    then_password_is_stored_only_as_a_hash,
    when_choose_auth_mode,
    when_set_up_local_admin,
)
from tests.functional.steps.login import then_directory_was_not_asked_again
from tests.functional.steps.session import then_me_is
from tests.functional.steps.setup import when_save_directory

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_choosing_local_mode_skips_the_directory_step(api: Api) -> None:
    """Scenario: 1단계에서 직접 관리를 고르면 AD 단계가 사라지고 저장 위치 단계가 남는다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_choose_auth_mode(api, "local")
    # Then
    then_status_is(response, 204)
    await then_auth_config_is(
        api,
        auth_mode="local",
        needs_directory_setup=False,
        needs_storage_setup=True,
        needs_admin_setup=False,
    )


async def test_local_three_step_setup_signs_in_the_first_admin(api: Api) -> None:
    """Scenario: 직접 관리로 저장 위치까지 마친 뒤 첫 admin을 등록하면 그 사람이 로그인된다."""
    # Given
    await given_local_storage_step_done(api)
    # When
    response = await when_set_up_local_admin(
        api, login_id="kim", display_name="김관리", email="Kim@Corp.test", phone="010-1234-5678"
    )
    # Then
    then_status_is(response, 200)
    then_body_includes(response, subject="kim", role="admin", name="김관리", email="kim@corp.test")
    await then_me_is(api, subject="kim", role="admin")
    await then_auth_config_is(
        api, needs_directory_setup=False, needs_storage_setup=False, needs_admin_setup=False
    )
    await then_password_is_stored_only_as_a_hash(
        api, login_id="kim", password=local_password_of("kim")
    )
    then_directory_was_not_asked_again(api, calls_before=0)


async def test_storage_step_before_choosing_a_mode_is_409(api: Api) -> None:
    """Scenario: 인증 방식을 고르기 전에 저장 위치를 저장하면 409(먼저 인증 방식을 고르세요)다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await api.put(SETUP_STORAGE, json={"path": storage_path_of(api)})
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == AUTH_MODE_FIRST


async def test_weak_admin_password_is_422_and_setup_stays_open(api: Api) -> None:
    """Scenario: 8자 미만 비밀번호로 첫 admin을 등록하면 422이고 설정은 열린 채 남는다."""
    # Given
    await given_local_storage_step_done(api)
    # When
    response = await when_set_up_local_admin(api, password="short7!")  # noqa: S106
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_no_user_registered(api, login_id="root")
    await then_auth_config_is(api, needs_admin_setup=True)


async def test_admin_registration_without_a_name_is_422(api: Api) -> None:
    """Scenario: 이름 없이 첫 admin을 등록하면 422이고 설정은 열린 채 남는다."""
    # Given
    await given_local_storage_step_done(api)
    # When
    response = await when_set_up_local_admin(api, display_name="  ")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_no_user_registered(api, login_id="root")


async def test_saving_the_directory_after_choosing_local_switches_to_ad(api: Api) -> None:
    """Scenario: 직접 관리를 골랐더라도 admin 전에 AD 연결을 저장하면 인증 방식이 ad로 바뀐다."""
    # Given
    await given_auth_mode_chosen(api, "local")
    # When
    response = await when_save_directory(api)
    # Then
    then_status_is(response, 200)
    await then_auth_config_is(
        api, auth_mode="ad", needs_directory_setup=False, needs_storage_setup=True
    )


async def test_choosing_a_mode_after_the_first_admin_is_409(api: Api) -> None:
    """Scenario: 첫 admin이 있으면 인증 방식 선택은 409(설정이 닫혔다)이고 방식은 그대로다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    # When
    response = await when_choose_auth_mode(api, "local")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == SETUP_CLOSED
    await then_auth_config_is(api, auth_mode="ad")


async def test_an_invalid_mode_is_422(api: Api) -> None:
    """Scenario: 알 수 없는 인증 방식은 422(request-validation)이고 선택은 바뀌지 않는다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_choose_auth_mode(api, "oidc")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_auth_config_is(api, auth_mode=None)


async def test_ad_mode_setup_rejects_profile_fields(api: Api) -> None:
    """Scenario: AD 모드의 첫 admin 등록에 이름·이메일·전화를 보내면 422이고 AD를 부르지 않는다."""
    # Given
    from tests.functional.steps.auth import given_storage_configured  # noqa: PLC0415

    given_ad_account(api, login_id="kim")
    await given_auth_mode_chosen(api, "ad")
    await when_save_directory(api)
    await given_storage_configured(api)
    # When
    response = await when_set_up_local_admin(
        api,
        login_id="kim",
        password="pw-kim",  # noqa: S106
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_directory_was_not_asked_again(api, calls_before=0)
