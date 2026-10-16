"""Feature: 등록된 사용자는 로그인하고, 삭제되면 즉시 차단되며 재등록해도 옛 세션은 죽은 채다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import ME, given_user_registered
from tests.functional.steps.common import then_status_is
from tests.functional.steps.rereads import then_listed_user_has_recent_last_login
from tests.functional.steps.users import (
    BUSINESS_READ,
    given_signed_in_session,
    given_user_deleted,
    id_of,
    when_login,
    when_register_user,
    when_request_as,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_a_registered_user_logs_in_and_the_last_login_time_is_recorded(api: Api) -> None:
    """Scenario: 등록된 사용자가 AD 비밀번호로 로그인하면 업무 API를 쓰고 로그인 시각이 남는다."""
    # Given
    await given_user_registered(api, login_id="kim", role="sales")
    # When
    response = await when_login(api, "kim")
    # Then
    then_status_is(response, 200)
    then_status_is(await api.get(BUSINESS_READ), 200)
    await then_listed_user_has_recent_last_login(api, "kim", viewer="root")


async def test_a_deleted_user_is_blocked_at_once_including_a_new_login(api: Api) -> None:
    """Scenario: 삭제된 사용자는 AD 계정이 남아 있어도 다시 로그인할 수 없다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    assert (await when_request_as(api, kim, "GET", ME)).status_code == 200
    await given_user_deleted(api, await id_of(api, "kim"))
    # When
    response = await when_login(api, "kim")
    # Then
    then_status_is(response, 401)


async def test_old_session_stays_dead_after_the_same_login_id_is_registered_again(
    api: Api,
) -> None:
    """Scenario: 같은 아이디로 다시 등록해도 삭제 전에 받은 세션은 계속 401이다."""
    # Given
    old_session = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_user_deleted(api, await id_of(api, "kim"))
    assert (await when_register_user(api, login_id="kim", role="sales")).status_code == 201
    # When
    response = await when_request_as(api, old_session, "GET", BUSINESS_READ)
    # Then
    then_status_is(response, 401)


async def test_a_re_registered_user_can_log_in_again(api: Api) -> None:
    """Scenario: 삭제 뒤 같은 아이디로 다시 등록된 사용자는 새로 로그인할 수 있다."""
    # Given
    await given_signed_in_session(api, login_id="kim", role="sales")
    await given_user_deleted(api, await id_of(api, "kim"))
    assert (await when_register_user(api, login_id="kim", role="sales")).status_code == 201
    # When
    response = await when_login(api, "kim")
    # Then
    then_status_is(response, 200)
