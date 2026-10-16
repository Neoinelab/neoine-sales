"""Feature: 사용자의 역할은 세션이 아니라 users 표에서 매 요청 읽으므로 변경이 즉시 반영된다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from tests.functional.steps.auth import ME, USERS, given_logged_in_as
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.requests import when_request
from tests.functional.steps.users import (
    BUSINESS_PAYLOAD,
    BUSINESS_READ,
    BUSINESS_WRITE,
    given_signed_in_session,
    given_user_deleted,
    id_of,
    when_register_user,
    when_request_as,
)
from tests.functional.steps.users_db import given_role_changed

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("method", "url", "payload", "expected"),
    [
        ("GET", USERS, None, 403),
        ("POST", BUSINESS_WRITE, BUSINESS_PAYLOAD, 403),
        ("GET", BUSINESS_READ, None, 200),
    ],
)
async def test_a_demoted_admin_loses_admin_access_on_the_next_request(
    api: Api, method: str, url: str, payload: object, expected: int
) -> None:
    """Scenario: admin에서 조회 사용자로 내려가면 관리·쓰기는 403이고 조회는 그대로다."""
    # Given
    boss = await given_signed_in_session(api, login_id="boss", role="admin")
    assert (await when_request_as(api, boss, "GET", USERS)).status_code == 200
    await given_role_changed(api, login_id="boss", role=Role.USER)
    # When
    response = await when_request_as(api, boss, method, url, json=payload)
    # Then
    then_status_is(response, expected)


async def test_a_promoted_sales_user_gains_admin_access_on_the_next_request(api: Api) -> None:
    """Scenario: 영업 사용자가 admin으로 올라가면 다음 요청부터 사용자 관리를 쓸 수 있다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    assert (await when_request_as(api, kim, "GET", USERS)).status_code == 403
    await given_role_changed(api, login_id="kim", role=Role.ADMIN)
    # When
    response = await when_request_as(api, kim, "GET", USERS)
    # Then
    then_status_is(response, 200)


async def test_a_viewer_promoted_to_sales_can_write_immediately(api: Api) -> None:
    """Scenario: 조회 사용자가 영업으로 올라가면 다음 요청부터 쓰기가 된다."""
    # Given
    lee = await given_signed_in_session(api, login_id="lee", role="user")
    before = await when_request_as(api, lee, "POST", BUSINESS_WRITE, json=BUSINESS_PAYLOAD)
    assert before.status_code == 403
    await given_role_changed(api, login_id="lee", role=Role.SALES)
    # When
    response = await when_request_as(api, lee, "POST", BUSINESS_WRITE, json=BUSINESS_PAYLOAD)
    # Then
    then_status_is(response, 201)


async def test_the_role_recorded_in_the_session_is_ignored(api: Api) -> None:
    """Scenario: 로그인 때의 역할이 세션에 남아 있어도 현재 권한은 users 표의 역할이다."""
    # Given
    sneaky = await given_signed_in_session(api, login_id="sneaky", role="admin")
    await given_role_changed(api, login_id="sneaky", role=Role.USER)
    # When
    response = await when_request_as(api, sneaky, "GET", ME)
    # Then
    then_body_includes(response, role="user", subject="sneaky")


async def test_a_role_changed_by_deleting_and_registering_again_applies_at_once(api: Api) -> None:
    """Scenario: 수정 API가 없어 삭제 후 다른 역할로 재등록하면 옛 세션은 폐기되어 401이다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_user_deleted(api, await id_of(api, "kim"))
    assert (await when_register_user(api, login_id="kim", role="user")).status_code == 201
    # When
    response = await when_request_as(api, kim, "GET", BUSINESS_READ)
    # Then
    then_status_is(response, 401)


async def test_forbidden_responses_are_problem_json_with_a_readable_detail(api: Api) -> None:
    """Scenario: 권한이 없으면 403 Problem 응답에 읽을 수 있는 사유가 담긴다."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_request(api, "POST", BUSINESS_WRITE, json=BUSINESS_PAYLOAD)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["status"] == 403
    assert response.json()["detail"].strip()
