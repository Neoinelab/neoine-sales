"""Feature: AD 설정 행이 지워진 시스템(마이그레이션 직후)에서 최초 설정은 admin이 있으면 닫혀 있다.

AD 설정 개편 리비전은 기존 설정 행을 지운다. admin이 이미 있으면 아무나 자기 LDAP 서버를 등록해
admin이 되는 길이 열리지 않도록 최초 설정 1단계는 계속 닫히고, 설정은 admin이 관리 화면에서 새로
등록한다. admin이 없으면(최초 설치) 최초 설정이 그대로 열린다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED
from tests.functional.steps.auth import given_admin_exists, given_logged_out
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.login import (
    given_employee,
    then_auth_flags_are,
    when_log_in,
)
from tests.functional.steps.settings import given_settings_row_removed
from tests.functional.steps.setup import (
    then_setup_is_closed,
    when_read_auth_config,
    when_save_directory,
    when_setup_step_is_requested,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_auth_config_without_settings_but_with_an_admin_stays_closed(api: Api) -> None:
    """Scenario: admin이 있고 설정 행만 없으면 directory_login=false, 최초 설정은 필요 없다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    await given_settings_row_removed(api)
    # When
    response = await when_read_auth_config(api)
    # Then
    then_status_is(response, 200)
    then_body_includes(response, directory_login=False, needs_directory_setup=False)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=False, needs_admin=False)


@pytest.mark.parametrize("step", ["directory", "storage", "admin"])
async def test_setup_steps_are_closed_while_an_admin_exists(api: Api, step: str) -> None:
    """Scenario: 설정 행이 지워져 있어도 admin이 있으면 최초 설정 단계는 모두 409로 닫혀 있다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    await given_settings_row_removed(api)
    # When
    response = await when_setup_step_is_requested(api, step=step)
    # Then
    then_setup_is_closed(response)


async def test_first_step_stays_closed_and_stores_nothing(api: Api) -> None:
    """Scenario: 설정 행이 없는 시스템에 1단계를 요청하면 409이고 AD를 호출하지 않는다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    await given_settings_row_removed(api)
    api.directory.discover_calls.clear()
    # When
    response = await when_save_directory(api)
    # Then
    then_setup_is_closed(response)
    assert api.directory.discover_calls == []
    assert (await when_read_auth_config(api)).json()["directory_login"] is False


async def test_a_user_without_a_hash_cannot_sign_in_until_an_admin_registers_the_settings(
    api: Api,
) -> None:
    """Scenario: 설정도 해시도 없는 사용자의 로그인은 409 'AD 서버가 아직 등록되지 않았다'이다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_settings_row_removed(api)
    # When
    response = await when_log_in(api, login_id="kim")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_body_includes(response, detail=DIRECTORY_NOT_CONFIGURED)


async def test_a_fresh_system_without_users_or_settings_still_needs_the_directory_step(
    api: Api,
) -> None:
    """Scenario: 사용자도 설정도 없으면 최초 설치이므로 1단계가 열려 있다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_read_auth_config(api)
    # Then
    then_body_includes(response, directory_login=False, needs_directory_setup=True)
