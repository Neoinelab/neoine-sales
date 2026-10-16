"""Feature: 반복 실패한 로그인은 계정·IP 단위로 잠기고, 동시에 몰려도 한도를 넘지 않는다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.login import (
    ATTEMPT_LIMIT_PER_ACCOUNT,
    ATTEMPT_LIMIT_PER_IP,
    directory_call_count,
    given_employee,
    given_failed_logins,
    given_failed_logins_from_many_accounts,
    then_directory_was_not_asked_again,
    then_no_cookie_is_set,
    then_statuses_are_only,
    when_log_in,
    when_log_in_many_times,
)
from tests.functional.steps.login_db import then_no_failure_is_counted

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

PARALLEL = 20
DIRECTORY_DELAY = 0.1


async def test_account_lock_returns_429_without_asking_the_directory(api: Api) -> None:
    """Scenario: 한 계정이 5번 실패하면 올바른 비밀번호도 429이고 AD를 호출하지 않는다."""
    # Given
    await given_employee(api)
    await given_failed_logins(api, login_id="kim", count=ATTEMPT_LIMIT_PER_ACCOUNT)
    calls_before = directory_call_count(api)
    # When
    response = await when_log_in(api)
    # Then
    then_problem_is(response, status=429, type_suffix="too-many-attempts")
    then_no_cookie_is_set(response)
    then_directory_was_not_asked_again(api, calls_before=calls_before)


async def test_ip_lock_returns_429_even_for_a_new_account(api: Api) -> None:
    """Scenario: 한 IP에서 서로 다른 계정이 30번 실패하면 다른 계정의 로그인도 429이다."""
    # Given
    await given_employee(api)
    await given_failed_logins_from_many_accounts(api, count=ATTEMPT_LIMIT_PER_IP)
    # When
    response = await when_log_in(api)
    # Then
    then_problem_is(response, status=429, type_suffix="too-many-attempts")


async def test_successful_login_gives_back_the_reserved_attempt(api: Api) -> None:
    """Scenario: 로그인에 성공하면 미리 잡아 둔 시도가 반환되어 실패 횟수가 남지 않는다."""
    # Given
    await given_employee(api)
    # When
    response = await when_log_in(api)
    # Then
    then_status_is(response, 200)
    await then_no_failure_is_counted(api)


async def test_successful_logins_do_not_consume_the_ip_limit(api: Api) -> None:
    """Scenario: 성공한 로그인은 IP 한도를 소비하지 않아 한도 + 1번 연달아 성공한다."""
    # Given
    await given_employee(api)
    # When
    responses = await when_log_in_many_times(api, login_id="kim", times=ATTEMPT_LIMIT_PER_IP + 1)
    # Then
    then_statuses_are_only(responses, 200)


async def test_failure_counter_is_shared_between_app_instances(api: Api) -> None:
    """Scenario: 한 서버에서 쌓인 실패 횟수가 다른 서버 인스턴스에서도 계정을 잠근다."""
    # Given
    await given_employee(api)
    await given_failed_logins(api, login_id="kim", count=ATTEMPT_LIMIT_PER_ACCOUNT)
    await api.reopen()  # 같은 DB를 보는 다른 앱 인스턴스
    calls_before = directory_call_count(api)
    # When
    response = await when_log_in(api)
    # Then
    then_problem_is(response, status=429, type_suffix="too-many-attempts")
    then_directory_was_not_asked_again(api, calls_before=calls_before)
