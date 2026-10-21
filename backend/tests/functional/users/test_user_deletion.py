"""Feature: admin은 사용자를 삭제하고, 연결이 없으면 물리 삭제·보호 규칙은 어기지 않는다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import (
    ME,
    USERS,
    given_logged_in_as,
    given_user_registered,
)
from tests.functional.steps.common import then_body_is, then_problem_is, then_status_is
from tests.functional.steps.requests import when_get
from tests.functional.steps.rereads import then_session_is_rejected
from tests.functional.steps.users import (
    BUSINESS_READ,
    given_dev_login,
    given_signed_in_session,
    given_user_deleted,
    id_of,
    then_first_setup_stays_closed,
    then_logins_listed,
    when_delete_user,
    when_list_users,
    when_login,
    when_register_user,
    when_request_as,
)
from tests.functional.steps.users_db import (
    given_user_linked,
    given_user_resigned,
    then_no_session_rows,
)
from tests.functional.steps.users_given import given_deal_link_if, given_session_can_read
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_delete_without_links_returns_200_deleted_and_removes_the_user(api: Api) -> None:
    """Scenario: 연결된 행이 없는 사용자를 삭제하면 deleted이고 전체 목록에서도 사라진다."""
    # Given
    kim_id = await given_user_registered(api, login_id="kim", role="sales")
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_status_is(response, 200)
    then_body_is(response, {"outcome": "deleted"})
    await then_logins_listed(api, ["root"], status="all")


async def test_delete_accepts_the_reason_query(api: Api) -> None:
    """Scenario: reason=resigned 쿼리를 받아 삭제한다."""
    # Given
    kim_id = await given_user_registered(api, login_id="kim", role="sales")
    # When
    response = await when_delete_user(api, kim_id, reason="resigned")
    # Then
    then_status_is(response, 200)
    await then_logins_listed(api, ["root"])


async def test_delete_rejects_an_unknown_reason_and_keeps_the_user(api: Api) -> None:
    """Scenario: 알 수 없는 reason은 422 검증 오류이고 사용자는 그대로다."""
    # Given
    lee_id = await given_user_registered(api, login_id="lee", role="sales")
    # When
    response = await when_delete_user(api, lee_id, reason="fired")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_logins_listed(api, ["root", "lee"])


@pytest.mark.parametrize("linked", [False, True])
async def test_deleted_or_resigned_users_existing_session_is_rejected_from_the_next_request(
    api: Api, linked: bool
) -> None:
    """Scenario: 삭제·퇴사된 사용자의 기존 세션은 다음 요청부터 401이다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_session_can_read(api, kim, BUSINESS_READ)
    await given_deal_link_if(api, login_id="kim", linked=linked)
    kim_id = await id_of(api, "kim")
    await given_user_deleted(api, kim_id)
    # When
    business = await when_request_as(api, kim, "GET", BUSINESS_READ)
    # Then
    then_status_is(business, 401)
    await then_session_is_rejected(api, kim, ME)
    await then_no_session_rows(api, kim_id)


async def test_a_deleted_user_cannot_log_in_with_a_valid_ad_password(api: Api) -> None:
    """Scenario: 삭제된 사용자는 AD에 계정이 있어도 로그인할 수 없다(401)."""
    # Given
    kim_id = await given_user_registered(api, login_id="kim", role="sales")
    await given_user_deleted(api, kim_id)
    # When

    response = await when_login(api, "kim")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_deleting_a_resigned_user_again_is_409_invalid_state(api: Api) -> None:
    """Scenario: 이미 퇴사한 사용자의 재삭제는 409 invalid-state이고 사유에 퇴사가 적힌다."""
    # Given
    kim_id = await given_user_resigned(api, login_id="kim")
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert "퇴사" in response.json()["detail"]


async def test_deleting_a_physically_deleted_user_again_is_404_not_found(api: Api) -> None:
    """Scenario: 이미 물리 삭제된 사용자의 재삭제는 404 not-found다."""
    # Given
    kim_id = await given_user_registered(api, login_id="kim", role="sales")
    await given_user_deleted(api, kim_id)
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_delete_user_with_an_unknown_id_is_404_not_found(api: Api) -> None:
    """Scenario: 없는 id의 삭제는 404 not-found다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_user(api, MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_delete_user_with_a_malformed_id_is_422(api: Api) -> None:
    """Scenario: 정수 형식이 아닌 id는 422 검증 오류다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_user(api, "not-an-id")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("linked", [False, True])
async def test_an_admin_cannot_delete_themselves_whether_or_not_the_row_is_linked(
    api: Api, linked: bool
) -> None:
    """Scenario: admin이 둘 이상이어도 자기 자신은 삭제할 수 없고 세션은 유지된다."""
    # Given
    await given_user_registered(
        api, login_id="boss", role="admin"
    )  # 마지막 admin 규칙이 아닌 자기 삭제 규칙을 본다
    await given_deal_link_if(api, login_id="root", linked=linked)
    root_id = await id_of(api, "root")
    # When
    response = await when_delete_user(api, root_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert "자기 자신" in response.json()["detail"]
    then_status_is(await api.get(ME), 200)


async def test_the_only_admin_cannot_be_deleted(api: Api) -> None:
    """Scenario: 유일한 admin은 삭제할 수 없고(409) 세션도 유지된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    root_id = await id_of(api, "root")
    # When
    response = await when_delete_user(api, root_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_status_is(await api.get(ME), 200)


async def test_an_admin_can_delete_another_admin_while_two_exist(api: Api) -> None:
    """Scenario: admin이 둘이면 다른 admin을 삭제할 수 있다."""
    # Given
    boss_id = await given_user_registered(api, login_id="boss", role="admin")
    # When
    response = await when_delete_user(api, boss_id)
    # Then
    then_status_is(response, 200)
    await then_logins_listed(api, ["root"])


async def test_a_resigned_user_disappears_from_the_default_list(api: Api) -> None:
    """Scenario: 퇴사 처리된 사용자는 기본 목록에서 사라진다."""
    # Given
    boss_id = await given_user_registered(api, login_id="boss", role="sales")
    await given_user_linked(api, login_id="boss", kind="deal_owner")
    resigned = await when_delete_user(api, boss_id)
    # When
    default_list = await when_list_users(api)
    # Then
    then_body_is(resigned, {"outcome": "resigned"})
    assert [i["login_id"] for i in default_list.json()["items"]] == ["root"]


async def test_deleting_a_user_does_not_reopen_first_admin_setup(api: Api) -> None:
    """Scenario: 사용자를 지워도 최초 설정 화면이 다시 열리지 않는다."""
    # Given
    kim_id = await given_user_registered(api, login_id="kim", role="user")
    await given_user_deleted(api, kim_id)
    # When
    config = await when_get(api, "/api/v1/auth/config")
    # Then
    then_first_setup_stays_closed(config)


async def test_a_dev_login_admin_can_register_users(api: Api) -> None:
    """Scenario: 개발 로그인 admin이 등록하면 등록자는 개발 사용자 행으로 표시된다."""
    # Given
    await given_user_registered(api, login_id="kim", role="sales")
    await given_dev_login(api, "admin")
    # When
    response = await when_register_user(api, login_id="new", role="user")
    # Then
    then_status_is(response, 201)
    creator = response.json()["created_by"]
    assert creator["name"] == "개발 사용자(admin)"
    assert "login_id" not in creator
    assert creator["id"] == (await api.get(ME)).json()["user_id"]


async def test_a_dev_login_admin_can_delete_users(api: Api) -> None:
    """Scenario: 개발 로그인 admin은 사용자를 삭제할 수 있다."""
    # Given
    kim_id = await given_user_registered(api, login_id="kim", role="sales")
    await given_dev_login(api, "admin")
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_status_is(response, 200)


async def test_a_dev_login_admin_is_listed_as_a_regular_user(api: Api) -> None:
    """Scenario: 개발 로그인 admin은 일반 사용자 행으로 목록에 dev-admin으로 나온다."""
    # Given
    await given_user_registered(api, login_id="kim", role="sales")
    await given_dev_login(api, "admin")
    # When
    response = await when_get(api, USERS)
    # Then
    then_status_is(response, 200)
    assert "dev-admin" in [i["login_id"] for i in response.json()["items"]]
