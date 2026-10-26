"""Feature: admin은 재직 사용자의 역할을 바꾸고, 바뀐 역할은 다음 요청부터 적용된다.

세션은 지우지 않으므로 재로그인이 필요 없다. 자기 자신·퇴사자·개발 로그인 전용 사용자는 바꿀 수 없다
(409). 마지막 admin 강등 보호는 요청자도 재직 admin이어야 하므로 공개 API로는 도달하지 않는다(단위
테스트가 규칙을 고정한다). 판정 순서는 401 -> 403 -> 422/404 -> 409다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import ADMIN_LOGIN, USERS, given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_body_is, then_problem_is, then_status_is
from tests.functional.steps.deals import (
    given_deal,
    when_get_deal,
    when_list_deals,
)
from tests.functional.steps.requests import when_get
from tests.functional.steps.user_roles import (
    DEV_ONLY,
    RESIGNED,
    SELF_CHANGE,
    then_conflict_says,
    then_listed_role_is,
    then_my_role_is,
    then_role_is,
    when_change_role,
    when_change_role_as,
    when_change_role_with_body,
)
from tests.functional.steps.users import (
    BUSINESS_PAYLOAD,
    BUSINESS_READ,
    BUSINESS_WRITE,
    given_dev_login,
    given_signed_in_session,
    id_of,
    log_in,
    when_list_options,
    when_request_as,
)
from tests.functional.steps.users_db import given_user_resigned
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_changes_a_sales_user_to_user_and_the_same_session_loses_write(
    api: Api,
) -> None:
    """Scenario: sales를 user로 바꾸면 응답·목록에 새 역할이 보이고, 같은 세션의 쓰기는 403이다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    kim_id = await id_of(api, "kim")
    assert (
        await when_request_as(api, kim, "GET", BUSINESS_READ)
    ).status_code == 200  # 바뀌기 전에도 읽는 세션
    # When
    response = await when_change_role(api, kim_id, "user")
    # Then
    then_role_is(response, "user")
    assert (response.json()["id"], response.json()["login_id"]) == (kim_id, "kim")
    await then_listed_role_is(api, "kim", "user")
    write = await when_request_as(api, kim, "POST", BUSINESS_WRITE, json=BUSINESS_PAYLOAD)
    then_problem_is(write, status=403, type_suffix="forbidden")
    assert (await when_request_as(api, kim, "GET", BUSINESS_READ)).status_code == 200
    await then_my_role_is(api, kim, "user")


async def test_a_promoted_user_gains_admin_access_on_the_next_request(api: Api) -> None:
    """Scenario: user를 admin으로 올리면 같은 세션이 다음 요청부터 사용자 관리를 쓸 수 있다."""
    # Given
    lee = await given_signed_in_session(api, login_id="lee", role="user")
    lee_id = await id_of(api, "lee")
    assert (await when_request_as(api, lee, "GET", USERS)).status_code == 403
    # When
    response = await when_change_role(api, lee_id, "admin")
    # Then
    then_role_is(response, "admin")
    then_status_is(await when_request_as(api, lee, "GET", USERS), 200)


async def test_admin_can_demote_another_admin_while_another_remains(api: Api) -> None:
    """Scenario: 재직 admin이 둘이면 다른 admin을 sales로 내릴 수 있다."""
    # Given
    await given_signed_in_session(api, login_id="boss", role="admin")
    boss_id = await id_of(api, "boss")
    # When
    response = await when_change_role(api, boss_id, "sales")
    # Then
    then_role_is(response, "sales")
    await then_listed_role_is(api, "root", "admin")


async def test_admin_cannot_change_own_role(api: Api) -> None:
    """Scenario: 자기 자신의 역할은 409이고 역할은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_signed_in_session(api, login_id="boss", role="admin")  # 다른 admin이 있어도 막힌다
    root_id = await id_of(api, ADMIN_LOGIN)
    # When
    response = await when_change_role(api, root_id, "user")
    # Then
    then_conflict_says(response, SELF_CHANGE)
    await then_listed_role_is(api, "root", "admin")


async def test_resigned_user_role_cannot_be_changed(api: Api) -> None:
    """Scenario: 퇴사 처리된 사용자의 역할은 409이고 역할은 그대로다."""
    # Given
    gone_id = await given_user_resigned(api, login_id="gone", role="sales")
    # When
    response = await when_change_role(api, gone_id, "user")
    # Then
    then_conflict_says(response, RESIGNED)
    await then_listed_role_is(api, "gone", "sales")


async def test_dev_login_users_role_cannot_be_changed(api: Api) -> None:
    """Scenario: 개발 로그인 전용 사용자(dev-sales)의 역할은 409이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_dev_login(api, "sales")
    await log_in(api, ADMIN_LOGIN)
    dev_id = await id_of(api, "dev-sales")
    # When
    response = await when_change_role(api, dev_id, "user")
    # Then
    then_conflict_says(response, DEV_ONLY)
    await then_listed_role_is(api, "dev-sales", "sales")


async def test_same_role_returns_the_user_unchanged(api: Api) -> None:
    """Scenario: 지금과 같은 역할을 보내면 200이고 응답·목록 항목이 그대로다."""
    # Given
    await given_signed_in_session(api, login_id="kim", role="sales")
    kim_id = await id_of(api, "kim")
    before = next(
        item for item in (await when_get(api, USERS)).json()["items"] if item["login_id"] == "kim"
    )
    # When
    response = await when_change_role(api, kim_id, "sales")
    # Then
    then_status_is(response, 200)
    then_body_is(response, before)
    after = next(
        item for item in (await when_get(api, USERS)).json()["items"] if item["login_id"] == "kim"
    )
    assert after == before


async def test_non_admin_gets_403_and_the_role_is_unchanged(api: Api) -> None:
    """Scenario: admin이 아니면 403이고 대상의 역할은 그대로다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_signed_in_session(api, login_id="lee", role="user")
    lee_id = await id_of(api, "lee")
    # When
    response = await when_change_role_as(api, kim, lee_id, "admin")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_listed_role_is(api, "lee", "user")


async def test_unauthenticated_request_gets_401(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_change_role(api, MISSING_ID, "user")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_unknown_user_is_404(api: Api) -> None:
    """Scenario: 없는 id는 404 not-found이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_change_role(api, MISSING_ID, "user")
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", "1.5"])
async def test_malformed_user_id_is_422(api: Api, bad_id: str) -> None:
    """Scenario: 정수 id 형식이 아니면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_change_role(api, bad_id, "user")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize(
    "body",
    [{}, {"role": None}, {"role": "superuser"}, {"role": "ADMIN"}, {"role": "user", "name": "x"}],
)
async def test_invalid_role_body_is_422_and_the_role_is_unchanged(
    api: Api, body: dict[str, object]
) -> None:
    """Scenario: role이 없거나 admin/sales/user가 아니거나 모르는 필드가 있으면 422이다."""
    # Given
    await given_signed_in_session(api, login_id="kim", role="sales")
    kim_id = await id_of(api, "kim")
    # When
    response = await when_change_role_with_body(api, kim_id, body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_listed_role_is(api, "kim", "sales")


async def test_deals_of_a_former_sales_owner_stay_readable_and_owner_options_drop_him(
    api: Api,
) -> None:
    """Scenario: sales였던 Owner의 Deal은 그대로 조회되고, 새 Owner 후보에서는 빠진다."""
    # Given
    await given_signed_in_session(api, login_id="kim", role="sales")
    kim_id = await id_of(api, "kim")
    deal = await given_deal(api, owner_user_id=kim_id)
    # When
    response = await when_change_role(api, kim_id, "user")
    # Then
    then_role_is(response, "user")
    detail = await when_get_deal(api, deal["code"])
    then_status_is(detail, 200)
    assert detail.json()["owner"]["id"] == kim_id
    listed = await when_list_deals(api)
    assert [item["code"] for item in listed.json()["items"]] == [deal["code"]]
    options = await when_list_options(api, role="sales")
    assert kim_id not in [item["id"] for item in options.json()["items"]]
