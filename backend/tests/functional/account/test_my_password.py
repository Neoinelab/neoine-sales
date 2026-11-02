"""Feature: local 사용자는 현재 비밀번호를 확인하고 자기 비밀번호를 바꾼다.

지금 로그인은 유지하고 같은 사용자의 다른 기기 로그인은 종료한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.local_accounts import (
    given_ad_system_with_user,
    given_local_session,
    given_local_user_registered,
    local_password_of,
    then_session_is_alive,
    then_session_is_ended,
    when_change_my_password,
    when_get_me,
    when_log_in_local,
)
from tests.functional.steps.session import then_caller_is_anonymous

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NEW = "Fresh-passw0rd"


async def test_wrong_current_password_is_422_and_counted(api: Api) -> None:
    """Scenario: 현재 비밀번호가 틀리면 422(위치 current_password)이고 로그인 시도 실패로 센다."""
    # Given
    await given_local_user_registered(api, login_id="kim")
    await given_local_session(api, login_id="kim")
    # When
    responses = [
        await when_change_my_password(api, current="wrong-password-1", new=NEW)
        for _ in range(MAX_PER_ACCOUNT)
    ]
    locked = await when_change_my_password(api, current=local_password_of("kim"), new=NEW)
    # Then
    for response in responses:
        then_problem_is(response, status=422, type_suffix="invalid-value")
        assert [e["location"] for e in response.json()["errors"]] == [["current_password"]]
    then_problem_is(locked, status=429, type_suffix="too-many-attempts")
    then_status_is(await when_get_me(api), 200)  # 실패해도 로그아웃되지 않는다


async def test_changing_password_ends_other_sessions_only(api: Api) -> None:
    """Scenario: 비밀번호를 바꾸면 지금 세션은 유지되고 같은 사용자의 다른 세션은 끝난다."""
    # Given
    await given_local_user_registered(api, login_id="kim")
    other = await given_local_session(api, login_id="kim")
    current = await given_local_session(api, login_id="kim")
    # When
    response = await when_change_my_password(
        api, current=local_password_of("kim"), new=NEW, headers=current.headers
    )
    # Then
    then_status_is(response, 204)
    await then_session_is_alive(api, current)
    await then_session_is_ended(api, other)


async def test_new_password_signs_in_and_old_does_not(api: Api) -> None:
    """Scenario: 바꾼 뒤에는 새 비밀번호로만 로그인된다."""
    # Given
    await given_local_user_registered(api, login_id="kim")
    await given_local_session(api, login_id="kim")
    await when_change_my_password(api, current=local_password_of("kim"), new=NEW)
    # When
    old = await when_log_in_local(api, "kim")
    new = await when_log_in_local(api, "kim", NEW)
    # Then
    then_problem_is(old, status=401, type_suffix="unauthenticated")
    then_status_is(new, 200)


async def test_weak_new_password_is_422_on_the_new_password(api: Api) -> None:
    """Scenario: 8자 미만 새 비밀번호는 422(위치 new_password)이고 기존 비밀번호가 그대로다."""
    # Given
    await given_local_user_registered(api, login_id="kim")
    await given_local_session(api, login_id="kim")
    # When
    response = await when_change_my_password(api, current=local_password_of("kim"), new="short7!")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert [e["location"] for e in response.json()["errors"]] == [["new_password"]]
    then_status_is(await when_log_in_local(api, "kim"), 200)


async def test_ad_user_cannot_change_the_password(api: Api) -> None:
    """Scenario: AD 사용자가 비밀번호를 바꾸려 하면 409이다."""
    # Given
    await given_ad_system_with_user(api, login_id="kim")
    # When
    response = await when_change_my_password(api, current="pw-kim", new=NEW)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")


async def test_anonymous_cannot_change_a_password(api: Api) -> None:
    """Scenario: 로그인하지 않은 요청은 401이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_change_my_password(api, current="whatever-pass", new=NEW)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
    await then_caller_is_anonymous(api)
