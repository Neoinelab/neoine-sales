"""Feature: local 모드에서는 앱에 저장된 비밀번호로 로그인하고, AD는 전혀 부르지 않는다."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.functional.steps.auth import given_logged_out
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.local_accounts import (
    given_local_user_registered,
    given_local_user_resigned,
    local_password_of,
    when_log_in_local,
)
from tests.functional.steps.login import (
    directory_call_count,
    then_directory_was_not_asked_again,
    then_no_cookie_is_set,
)
from tests.functional.steps.session import then_me_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_a_registered_local_user_signs_in_with_the_password(api: Api) -> None:
    """Scenario: admin이 등록한 사용자가 그 비밀번호로 로그인하면 세션을 받고 경고는 없다."""
    # Given
    await given_local_user_registered(api, login_id="kim", role="sales", display_name="김영업")
    await given_logged_out(api)
    # When
    response = await when_log_in_local(api, "kim")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, subject="kim", role="sales", name="김영업", directory_warning=None)
    await then_me_is(api, subject="kim", role="sales")


async def test_wrong_password_and_unknown_id_get_the_same_401(api: Api) -> None:
    """Scenario: 틀린 비밀번호와 없는 아이디는 같은 401(같은 문구)이고 쿠키가 없다."""
    # Given
    await given_local_user_registered(api, login_id="kim")
    await given_logged_out(api)
    # When
    wrong = await when_log_in_local(api, "kim", "wrong-password-1")
    unknown = await when_log_in_local(api, "ghost", "wrong-password-1")
    # Then
    for response in (wrong, unknown):
        then_problem_is(response, status=401, type_suffix="unauthenticated")
        assert response.json()["detail"] == LOGIN_FAILED
        then_no_cookie_is_set(response)
    assert wrong.json()["detail"] == unknown.json()["detail"]


async def test_five_failures_lock_the_account_with_429(api: Api) -> None:
    """Scenario: 한 계정이 5번 실패하면 올바른 비밀번호도 429이다."""
    # Given
    await given_local_user_registered(api, login_id="kim")
    await given_logged_out(api)
    for _ in range(MAX_PER_ACCOUNT):
        await when_log_in_local(api, "kim", "wrong-password-1")
    # When
    response = await when_log_in_local(api, "kim")
    # Then
    then_problem_is(response, status=429, type_suffix="too-many-attempts")
    then_no_cookie_is_set(response)


async def test_a_resigned_local_user_cannot_sign_in(api: Api) -> None:
    """Scenario: 퇴사 처리된 사용자는 올바른 비밀번호로도 같은 401을 받는다."""
    # Given
    user_id = await given_local_user_registered(api, login_id="kim")
    await given_local_user_resigned(api, user_id=user_id)
    await given_logged_out(api)
    # When
    response = await when_log_in_local(api, "kim")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
    assert response.json()["detail"] == LOGIN_FAILED


async def test_local_login_never_contacts_the_directory(api: Api) -> None:
    """Scenario: local 모드의 로그인은 성공이든 실패든 AD(Port 대역)에 한 번도 가지 않는다."""
    # Given
    await given_local_user_registered(api, login_id="kim")
    await given_logged_out(api)
    calls_before = directory_call_count(api)
    # When
    await when_log_in_local(api, "kim", "wrong-password-1")
    response = await when_log_in_local(api, "kim", local_password_of("kim"))
    # Then
    then_status_is(response, 200)
    then_directory_was_not_asked_again(api, calls_before=calls_before)
    assert api.directory.discover_calls == []
