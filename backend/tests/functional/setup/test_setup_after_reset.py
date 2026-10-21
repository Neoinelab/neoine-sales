"""Feature: 전체 초기화(BIGINT id 리비전) 뒤 최초 설정 3단계가 다시 열리고 정수 id로 동작한다.

`fresh_api`는 마이그레이션만 적용한 새 임시 DB 위의 앱이다: 업무 데이터가 하나도 없고 시드만 있는
초기화된 시스템과 같다. 첫 admin의 등록자는 자기 자신이고(`created_by.id == id`), 그 뒤 로그인·
로그아웃이 동작한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import (
    USERS,
    given_ad_account,
    given_logged_out,
    given_setup_prerequisites_configured,
)
from tests.functional.steps.common import then_status_is
from tests.functional.steps.login import then_auth_flags_are
from tests.functional.steps.session import then_me_is
from tests.functional.steps.setup import (
    given_setup_completed_by,
    when_save_directory,
    when_set_up_admin,
)
from tests.functional.steps.users import when_login

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_a_reset_system_accepts_the_directory_step_again(fresh_api: Api) -> None:
    """Scenario: 초기화된 시스템에서 1단계(AD 연결 저장)가 409 없이 받아들여진다."""
    # Given
    # (마이그레이션 직후의 초기화된 시스템)
    # When
    response = await when_save_directory(fresh_api)
    # Then
    then_status_is(response, 200)
    await then_auth_flags_are(
        fresh_api, needs_directory=False, needs_storage=True, needs_admin=False
    )


async def test_admin_completes_first_setup_on_a_reset_database(fresh_api: Api) -> None:
    """Scenario: AD → 저장 위치 → 첫 admin 순서로 설정하면 첫 admin이 정수 id로 만들어진다."""
    # Given
    given_ad_account(fresh_api, login_id="kim", display_name="김관리", email="kim@corp.test")
    await given_setup_prerequisites_configured(fresh_api)
    # When
    response = await when_set_up_admin(fresh_api, login_id="kim")
    # Then
    then_status_is(response, 200)
    listed = (await fresh_api.get(USERS)).json()["items"]
    (admin,) = [item for item in listed if item["login_id"] == "kim"]
    assert type(admin["id"]) is int
    assert admin["id"] >= 1
    assert admin["role"] == "admin"
    assert admin["created_by"]["id"] == admin["id"]  # 첫 admin의 등록자는 자기 자신이다
    await then_me_is(fresh_api, user_id=admin["id"], subject="kim", role="admin")
    await then_auth_flags_are(
        fresh_api, needs_directory=False, needs_storage=False, needs_admin=False
    )


async def test_the_first_admin_can_log_out(fresh_api: Api) -> None:
    """Scenario: 초기화된 시스템의 첫 admin이 로그아웃하면 익명이 된다."""
    # Given
    await given_setup_completed_by(fresh_api, login_id="kim")
    # When
    await given_logged_out(fresh_api)
    # Then
    assert (await fresh_api.get("/api/v1/auth/me")).status_code == 401


async def test_the_first_admin_can_log_in_again(fresh_api: Api) -> None:
    """Scenario: 첫 admin이 로그아웃한 뒤 다시 로그인하면 같은 정수 id로 로그인된다."""
    # Given
    await given_setup_completed_by(fresh_api, login_id="kim")
    first_id = (await fresh_api.get("/api/v1/auth/me")).json()["user_id"]
    await given_logged_out(fresh_api)
    # When
    response = await when_login(fresh_api, "kim")
    # Then
    then_status_is(response, 200)
    assert response.json()["user_id"] == first_id
    assert type(first_id) is int
