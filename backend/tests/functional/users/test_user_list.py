"""Feature: admin은 사용자 목록을 상태별로 조회하고 페이지로 넘겨 볼 수 있다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import ADMIN_LOGIN, given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.users import (
    USER_KEYS,
    USER_REF_KEYS,
    given_user_deleted,
    then_is_scenario_now,
    then_logins_are,
    when_list_users,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_list_users_shows_the_documented_fields_without_any_password(api: Api) -> None:
    """Scenario: 목록 행은 문서화된 필드만 담고 비밀번호 관련 필드가 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_list_users(api)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == {"items", "offset", "limit"}
    (root,) = body["items"]
    assert set(root) == USER_KEYS
    assert (root["login_id"], root["role"]) == (ADMIN_LOGIN, "admin")
    assert set(root["created_by"]) == USER_REF_KEYS
    assert root["created_by"]["id"] == root["id"]  # 최초 admin은 스스로 등록한 행
    assert root["created_by"]["name"] == root["display_name"]
    assert (root["status"], root["deleted_at"], root["delete_reason"]) == ("active", None, None)
    assert not any("password" in key.lower() for key in root)


async def test_list_users_shows_the_last_login_time_and_null_when_never_logged_in(api: Api) -> None:
    """Scenario: 로그인한 사용자는 마지막 로그인 시각이 있고 한 번도 안 한 사용자는 비어 있다."""
    # Given
    await given_user_registered(api, login_id="fresh", role="user")
    # When
    response = await when_list_users(api)
    # Then
    then_status_is(response, 200)
    items = {item["login_id"]: item for item in response.json()["items"]}
    then_is_scenario_now(items["root"]["last_login_at"])
    assert items["root"]["display_name"]
    assert items["fresh"]["last_login_at"] is None
    assert items["fresh"]["display_name"] is None


async def test_list_users_hides_deleted_users_and_keeps_creation_order(api: Api) -> None:
    """Scenario: 삭제된 사용자는 목록에서 사라지고 나머지는 등록 순서를 지킨다."""
    # Given
    await given_user_registered(api, login_id="amy", role="sales")
    bob = await given_user_registered(api, login_id="bob", role="user")
    await given_user_deleted(api, bob)
    # When
    response = await when_list_users(api)
    # Then
    then_logins_are(response, ["root", "amy"])


async def test_list_users_pages_with_offset_and_limit(api: Api) -> None:
    """Scenario: offset과 limit으로 한 페이지만 받고 응답에 그 값이 되돌아온다."""
    # Given
    await given_user_registered(api, login_id="amy", role="sales")
    await given_user_registered(api, login_id="bob", role="user")
    # When
    response = await when_list_users(api, offset=1, limit=1)
    # Then
    then_logins_are(response, ["amy"])
    assert (response.json()["offset"], response.json()["limit"]) == (1, 1)


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 201}, {"limit": "x"}])
async def test_list_users_rejects_invalid_paging(api: Api, params: dict[str, str | int]) -> None:
    """Scenario: 범위를 벗어난 페이지 값은 422 검증 오류다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_list_users(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
