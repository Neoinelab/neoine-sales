"""Feature: 개발 환경에서는 AD 없이 역할별 개발용 로그인을 쓰고, 꺼진 환경에서는 그 기능이 없다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import CONFIG
from tests.functional.steps.common import then_body_includes, then_status_is
from tests.functional.steps.rereads import then_token_is_rejected
from tests.functional.steps.session import (
    SESSION_COOKIE,
    then_me_is,
    when_dev_login,
    when_get_with_session,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_dev_login_signs_in_with_each_role(api: Api, role: str) -> None:
    """Scenario: 개발용 로그인은 역할별 dev-<role> 사용자(users 행)로 로그인시킨다."""
    # Given
    # (개발용 로그인이 켜진 local 환경)
    # When
    response = await when_dev_login(api, role=role)
    # Then
    then_status_is(response, 200)
    then_body_includes(response, role=role, subject=f"dev-{role}")
    await then_me_is(api, role=role, subject=f"dev-{role}")
    user_id = (await api.get("/api/v1/auth/me")).json()["user_id"]
    assert type(user_id) is int
    assert user_id >= 1


async def test_dev_login_reuses_the_same_user_row_each_time(api: Api) -> None:
    """Scenario: 같은 역할로 개발용 로그인을 다시 해도 같은 사용자 행(id)을 쓴다."""
    # Given
    await when_dev_login(api, role="sales")
    first_id = (await api.get("/api/v1/auth/me")).json()["user_id"]
    # When
    response = await when_dev_login(api, role="sales")
    # Then
    then_status_is(response, 200)
    await then_me_is(api, user_id=first_id)


async def test_dev_login_rejects_unknown_roles(api: Api) -> None:
    """Scenario: 모르는 역할로 개발용 로그인을 요청하면 422이다."""
    # Given
    # (개발용 로그인이 켜진 local 환경)
    # When
    response = await when_dev_login(api, role="root")
    # Then
    then_status_is(response, 422)


async def test_dev_login_does_not_exist_when_disabled(api: Api) -> None:
    """Scenario: 개발용 로그인이 꺼진 환경에는 그 경로 자체가 없고 설정도 꺼짐으로 보인다."""
    # Given
    await api.reopen(dev_login_enabled=False)
    # When
    response = await when_dev_login(api, role="admin")
    # Then
    then_status_is(response, 404)
    then_body_includes(await api.get(CONFIG), dev_login=False)


async def test_dev_sessions_are_rejected_when_dev_login_is_not_allowed(api: Api) -> None:
    """Scenario: 개발용 로그인으로 받은 세션은 그 기능이 꺼진 환경에서 더는 통하지 않는다."""
    # Given
    token = (await when_dev_login(api, role="admin")).cookies[SESSION_COOKIE]
    await api.reopen(dev_login_enabled=False)
    # When
    response = await when_get_with_session(api, "/api/v1/auth/me", token=token)
    # Then
    then_status_is(response, 401)
    await then_token_is_rejected(api, "/api/v1/deals", token=token)
