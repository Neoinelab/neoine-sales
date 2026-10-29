"""Feature: AD 장애 중 AD 로그인 이력이 있는 사용자는 그때 비밀번호로 들어오고 admin은 경고를 본다.

대체 로그인은 AD가 답할 수 없을 때만(연결·TLS·서비스 계정·Base DN·검색 오류·설정 없음) 동작한다.
AD가 응답해 비밀번호가 틀렸다고 하면 저장된 비밀번호가 맞아도 거부한다. 대체 로그인에 실패하면
원래의 AD 불가 응답(503, 설정 없음이면 409)을 그대로 받고 실패 1회로 센다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED
from tests.functional.steps.auth import ADMIN_LOGIN, given_admin_exists, given_logged_out
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.fallback import (
    OUTAGES,
    given_directory_is_down,
    given_directory_recovers,
    given_directory_settings_are_missing,
    given_signed_in_through_directory_once,
    then_login_is_refused_as_unavailable,
    then_signed_in_with_warning,
    then_signed_in_without_warning,
    when_log_in_with_the_directory_password,
)
from tests.functional.steps.login import (
    ATTEMPT_LIMIT_PER_ACCOUNT,
    given_employee,
    then_failure_count_is,
    then_password_hash_is_stored_for,
    when_log_in,
)
from tests.functional.steps.session import then_me_is, then_session_cookie_is_http_only_lax
from tests.functional.steps.users_db import given_user_resigned

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

STAGES = list(OUTAGES)


async def test_sales_user_logs_in_with_the_stored_password_while_the_directory_is_down(
    api: Api,
) -> None:
    """Scenario: AD 연결이 안 되어도 AD로 로그인한 적이 있는 sales 사용자는 들어오고 경고는 없다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_signed_in_through_directory_once(api, login_id="kim")
    await given_directory_is_down(api, stage="connect")
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_signed_in_without_warning(response)
    then_session_cookie_is_http_only_lax(response)
    await then_me_is(api, subject="kim", role="sales")


@pytest.mark.parametrize("stage", STAGES)
async def test_admin_gets_a_warning_naming_the_failed_stage(api: Api, stage: str) -> None:
    """Scenario: admin이 대체 로그인으로 들어오면 응답에 실패 단계와 안내 문구가 담긴다."""
    # Given
    await given_admin_exists(api)  # 최초 설정 3단계의 AD 인증으로 admin 해시가 저장된다
    await given_logged_out(api)
    await given_directory_is_down(api, stage=stage)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id=ADMIN_LOGIN)
    # Then
    then_signed_in_with_warning(response, stage=stage)
    await then_me_is(api, subject=ADMIN_LOGIN, role="admin")


async def test_admin_login_without_directory_settings_warns_that_nothing_is_configured(
    api: Api,
) -> None:
    """Scenario: AD 설정이 없어도 해시가 있는 admin은 들어오고 not_configured 경고를 받는다."""
    # Given
    await given_admin_exists(api)
    await given_logged_out(api)
    await given_directory_settings_are_missing(api)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id=ADMIN_LOGIN)
    # Then
    then_signed_in_with_warning(response, stage="not_configured")


@pytest.mark.parametrize("role", ["sales", "user"])
async def test_non_admin_fallback_login_has_no_warning(api: Api, role: str) -> None:
    """Scenario: admin이 아닌 사용자는 설정이 없을 때도 경고 없이 들어온다."""
    # Given
    await given_employee(api, login_id="kim", role=role)  # type: ignore[arg-type]
    await given_signed_in_through_directory_once(api, login_id="kim")
    await given_directory_settings_are_missing(api)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_signed_in_without_warning(response)


async def test_fallback_login_keeps_the_stored_hash_and_profile(api: Api) -> None:
    """Scenario: 대체 로그인은 해시와 프로필을 바꾸지 않는다(최근 로그인 시각만 갱신)."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_signed_in_through_directory_once(api, login_id="kim")
    before = await then_password_hash_is_stored_for(api, login_id="kim", password="pw-kim")  # noqa: S106 - 가짜 값
    await given_directory_is_down(api)
    api.clock.advance(3600)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_signed_in_without_warning(response)
    assert response.json()["name"] == "김영업"
    assert await then_password_hash_is_stored_for(api, login_id="kim", password="pw-kim") == before  # noqa: S106 - 가짜 값


async def test_after_the_directory_recovers_the_next_login_goes_through_it_again(
    api: Api,
) -> None:
    """Scenario: AD가 돌아오면 다음 로그인은 AD를 거치고 해시가 새 솔트로 갱신된다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_signed_in_through_directory_once(api, login_id="kim")
    first = await then_password_hash_is_stored_for(api, login_id="kim", password="pw-kim")  # noqa: S106 - 가짜 값
    await given_directory_is_down(api)
    assert (await when_log_in_with_the_directory_password(api, login_id="kim")).status_code == 200
    await given_logged_out(api)
    given_directory_recovers(api)
    api.directory.authenticate_calls.clear()
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_signed_in_without_warning(response)
    assert len(api.directory.authenticate_calls) == 1
    assert await then_password_hash_is_stored_for(api, login_id="kim", password="pw-kim") != first  # noqa: S106 - 가짜 값


async def test_wrong_password_while_the_directory_is_down_is_503_and_counted(api: Api) -> None:
    """Scenario: AD 장애 중 틀린 비밀번호는 AD 불가 응답(503)과 같고 실패 1회로 센다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_signed_in_through_directory_once(api, login_id="kim")
    await given_directory_is_down(api)
    # When
    response = await when_log_in(api, login_id="kim", password="wrong-password")  # noqa: S106 - 가짜 값
    # Then
    then_login_is_refused_as_unavailable(response)
    await then_failure_count_is(api, 1)


async def test_user_without_a_stored_hash_gets_the_same_503(api: Api) -> None:
    """Scenario: AD로 로그인한 적이 없는 사용자는 장애 중 503이고 실패 1회로 센다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")  # 한 번도 AD로 로그인하지 않았다
    await given_directory_is_down(api)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_login_is_refused_as_unavailable(response)
    await then_failure_count_is(api, 1)


async def test_unknown_user_gets_the_same_503_as_a_user_without_a_hash(api: Api) -> None:
    """Scenario: 미등록 아이디와 해시 없는 사용자의 응답이 같아 계정 존재 여부를 알 수 없다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_directory_is_down(api)
    # When
    known = await when_log_in_with_the_directory_password(api, login_id="kim")
    unknown = await when_log_in(api, login_id="ghost", password="pw-ghost")  # noqa: S106 - 가짜 값
    # Then
    then_login_is_refused_as_unavailable(known)
    then_login_is_refused_as_unavailable(unknown)
    assert known.json()["detail"] == unknown.json()["detail"]
    assert known.status_code == unknown.status_code


async def test_resigned_user_cannot_use_the_stored_password(api: Api) -> None:
    """Scenario: 퇴사 처리된 사용자는 장애 중에도 들어올 수 없다(해시도 지워진다)."""
    # Given
    await given_user_resigned(api, login_id="kim", role="sales")
    await given_directory_is_down(api)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_login_is_refused_as_unavailable(response)


async def test_without_settings_and_without_a_hash_the_login_is_409(api: Api) -> None:
    """Scenario: 설정도 해시도 없으면 'AD 서버가 아직 등록되지 않았습니다' 409이고 실패 1회다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_directory_settings_are_missing(api)
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_body_includes(response, detail=DIRECTORY_NOT_CONFIGURED)
    await then_failure_count_is(api, 1)


async def test_repeated_failures_lock_the_account_even_for_the_right_password(api: Api) -> None:
    """Scenario: 장애 중 실패가 제한 횟수에 이르면 올바른 비밀번호도 429로 막힌다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_signed_in_through_directory_once(api, login_id="kim")
    await given_directory_is_down(api)
    for _ in range(ATTEMPT_LIMIT_PER_ACCOUNT):
        await when_log_in(api, login_id="kim", password="wrong-password")  # noqa: S106 - 가짜 값
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_problem_is(response, status=429, type_suffix="too-many-attempts")


async def test_directory_rejection_is_never_overridden_by_the_stored_hash(api: Api) -> None:
    """Scenario: AD가 응답해 비밀번호를 거부하면 저장된 해시와 같은 비밀번호도 401이다."""
    # Given
    await given_employee(api, login_id="kim", role="sales")
    await given_signed_in_through_directory_once(api, login_id="kim")
    api.directory.add_account("kim", "changed-in-directory-1!")
    # When
    response = await when_log_in_with_the_directory_password(api, login_id="kim")
    # Then
    then_status_is(response, 401)
    assert "directory_warning" not in response.text
