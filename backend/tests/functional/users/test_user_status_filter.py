"""Feature: admin은 재직·퇴사 상태로 사용자를 걸러 보고, 퇴사한 아이디를 다시 등록할 수 있다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.rereads import then_login_row_count_is, then_login_rows_are
from tests.functional.steps.users import (
    given_user_signed_in_once,
    id_of,
    log_in,
    then_is_scenario_now,
    then_logins_are,
    then_logins_listed,
    when_list_users,
    when_register_user,
)
from tests.functional.steps.users_db import given_user_linked, given_user_resigned

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("params", [{}, {"status": "active"}])
async def test_status_defaults_to_active_and_hides_resigned_users(
    api: Api, params: dict[str, str]
) -> None:
    """Scenario: 상태 필터 기본값(active)은 퇴사자를 숨긴다."""
    # Given
    await given_user_resigned(api, login_id="kim")
    await given_user_registered(api, login_id="lee", role="user")
    # When
    response = await when_list_users(api, **params)
    # Then
    then_logins_are(response, ["root", "lee"])


async def test_status_resigned_lists_only_resigned_users_with_time_and_reason(api: Api) -> None:
    """Scenario: status=resigned는 퇴사자만 퇴사 시각·사유와 함께 보여 준다."""
    # Given
    kim_id = await given_user_resigned(api, login_id="kim")
    # When
    response = await when_list_users(api, status="resigned")
    # Then
    then_status_is(response, 200)
    (kim,) = response.json()["items"]
    assert kim["id"] == kim_id
    assert kim["status"] == "resigned"
    assert kim["delete_reason"] == "resigned"
    then_is_scenario_now(kim["deleted_at"])


async def test_status_all_lists_everyone_in_creation_order(api: Api) -> None:
    """Scenario: status=all은 재직자와 퇴사자를 등록 순서대로 모두 보여 준다."""
    # Given
    await given_user_resigned(api, login_id="kim")
    await given_user_registered(api, login_id="lee", role="user")
    # When
    response = await when_list_users(api, status="all")
    # Then
    then_status_is(response, 200)
    items = response.json()["items"]
    assert [(i["login_id"], i["status"]) for i in items] == [
        ("root", "active"),
        ("kim", "resigned"),
        ("lee", "active"),
    ]
    assert items[0]["deleted_at"] is None
    assert items[0]["delete_reason"] is None


@pytest.mark.parametrize("status", ["", "ALL", "deleted", "retired", "1"])
async def test_invalid_status_is_422_request_validation(api: Api, status: str) -> None:
    """Scenario: 알 수 없는 상태 값은 422 검증 오류다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_list_users(api, status=status)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_status_all_paginates(api: Api) -> None:
    """Scenario: status=all도 offset·limit으로 페이지를 넘긴다."""
    # Given
    await given_user_resigned(api, login_id="kim")
    await given_user_registered(api, login_id="lee", role="user")
    # When
    response = await when_list_users(api, status="all", offset=1, limit=1)
    # Then
    then_logins_are(response, ["kim"])


async def test_registering_a_resigned_login_id_again_creates_a_new_row(api: Api) -> None:
    """Scenario: 퇴사한 아이디를 다시 등록하면 새 행이 생기고 퇴사 행은 그대로 남는다."""
    # Given
    old_id = await given_user_resigned(api, login_id="kim")
    # When
    response = await when_register_user(api, login_id="kim", role="user")
    # Then
    then_status_is(response, 201)
    assert response.json()["id"] != old_id
    assert response.json()["status"] == "active"
    await then_login_rows_are(api, "kim", [(old_id, "resigned"), (response.json()["id"], "active")])
    await then_logins_listed(api, ["root", "kim"])


async def test_registering_an_active_login_id_is_409_even_with_resigned_rows(api: Api) -> None:
    """Scenario: 퇴사 행이 있어도 재직 중인 아이디의 재등록은 409이고 행은 둘뿐이다."""
    # Given
    await given_user_resigned(api, login_id="kim")
    assert (await when_register_user(api, login_id="kim", role="user")).status_code == 201
    # When
    again = await when_register_user(api, login_id="KIM", role="sales")
    # Then
    then_problem_is(again, status=409, type_suffix="already-exists")
    await then_login_row_count_is(api, "kim", 2)  # 퇴사 행 하나 + 재직 행 하나


async def test_a_user_registered_by_a_resigned_admin_shows_the_creator_as_resigned(
    api: Api,
) -> None:
    """Scenario: 퇴사한 admin이 등록한 사용자의 등록자는 '(퇴사)'로 표시된다."""
    # Given
    await given_user_signed_in_once(api, login_id="boss", role="admin")
    await log_in(api, "boss")
    assert (await when_register_user(api, login_id="newbie", role="user")).status_code == 201
    await log_in(api, "root")
    await given_user_linked(api, login_id="boss", kind="deal_owner")
    assert (await api.delete(f"/api/v1/users/{await id_of(api, 'boss')}")).status_code == 200
    # When
    response = await when_list_users(api)
    # Then
    then_status_is(response, 200)
    newbie = next(i for i in response.json()["items"] if i["login_id"] == "newbie")
    creator = newbie["created_by"]
    assert creator["resigned"] is True
    assert creator["label"] == f"{creator['name']}(퇴사)"
