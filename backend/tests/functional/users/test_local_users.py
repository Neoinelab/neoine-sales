"""Feature: local 모드에서 admin은 사용자를 비밀번호와 함께 등록하고 정보·비밀번호를 관리한다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_ad_account, given_user_registered
from tests.functional.steps.common import (
    then_body_includes,
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.local_accounts import (
    ADMIN_LOGIN,
    given_local_admin_logged_in,
    given_local_session,
    given_local_user_registered,
    local_password_of,
    log_in_local,
    then_body_has_no_password,
    then_no_user_registered,
    then_password_is_stored_only_as_a_hash,
    then_session_is_alive,
    then_session_is_ended,
    user_body,
    when_get_me,
    when_list_users,
    when_log_in_local,
    when_patch_user,
    when_register_local_user,
    when_reset_password,
)
from tests.functional.steps.users import USER_KEYS, id_of

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_registers_a_user_who_can_then_sign_in(api: Api) -> None:
    """Scenario: admin이 아이디·비밀번호·이름·이메일·전화로 등록한 사용자가 로그인된다."""
    # Given
    await given_local_admin_logged_in(api)
    # When
    response = await when_register_local_user(
        api,
        user_body("kim", "sales", email="Kim@Corp.test", phone="010-1234-5678"),
    )
    # Then
    then_status_is(response, 201)
    assert set(response.json()) == USER_KEYS
    then_body_includes(
        response,
        login_id="kim",
        role="sales",
        display_name="사용자 kim",
        email="kim@corp.test",
        phone="010-1234-5678",
    )
    then_body_has_no_password(response, local_password_of("kim"))
    await then_password_is_stored_only_as_a_hash(
        api, login_id="kim", password=local_password_of("kim")
    )
    login = await when_log_in_local(api, "kim")
    then_status_is(login, 200)


async def test_registration_without_password_in_local_mode_is_422(api: Api) -> None:
    """Scenario: local 모드에서 비밀번호 없이 등록하면 422이고 사용자는 만들어지지 않는다."""
    # Given
    await given_local_admin_logged_in(api)
    body = user_body("kim")
    del body["password"]
    # When
    response = await when_register_local_user(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_no_user_registered(api, login_id="kim")


async def test_weak_password_registration_is_422(api: Api) -> None:
    """Scenario: 8자 미만 비밀번호로 등록하면 422이고 사용자는 만들어지지 않는다."""
    # Given
    await given_local_admin_logged_in(api)
    # When
    response = await when_register_local_user(
        api,
        user_body("kim", password="short7!"),  # noqa: S106
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_no_user_registered(api, login_id="kim")


async def test_password_in_ad_mode_registration_is_422(api: Api) -> None:
    """Scenario: AD 모드에서 비밀번호를 보내 등록하면 422이다(AD가 인증한다)."""
    # Given
    await given_user_registered(api, login_id="seed", role="sales")  # AD 모드로 admin(root) 로그인
    given_ad_account(api, login_id="kim")
    # When
    response = await when_register_local_user(api, user_body("kim"))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_no_user_registered(api, login_id="kim")


async def test_reset_password_ends_the_users_sessions(api: Api) -> None:
    """Scenario: 비밀번호를 재설정하면 그 사용자의 로그인이 끝나고 새 비밀번호로만 들어간다."""
    # Given
    user_id = await given_local_user_registered(api, login_id="kim")
    kim = await given_local_session(api, login_id="kim")
    await log_in_local(api, ADMIN_LOGIN)
    # When
    response = await when_reset_password(api, user_id, "Fresh-passw0rd")
    # Then
    then_status_is(response, 204)
    await then_session_is_ended(api, kim)
    assert (await when_log_in_local(api, "kim")).status_code == 401  # 이전 비밀번호
    assert (await when_log_in_local(api, "kim", "Fresh-passw0rd")).status_code == 200


async def test_admin_cannot_reset_own_password(api: Api) -> None:
    """Scenario: admin이 자기 자신의 비밀번호를 재설정하면 409이고 기존 비밀번호가 그대로다."""
    # Given
    await given_local_admin_logged_in(api)
    admin_id = await id_of(api, ADMIN_LOGIN)
    # When
    response = await when_reset_password(api, admin_id, "Fresh-passw0rd")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert (await when_get_me(api)).status_code == 200


async def test_reset_password_in_ad_mode_is_409(api: Api) -> None:
    """Scenario: AD 모드에서는 비밀번호 재설정이 409이다."""
    # Given
    user_id = await given_user_registered(api, login_id="kim", role="sales")
    # When
    response = await when_reset_password(api, user_id, "Fresh-passw0rd")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")


async def test_weak_reset_password_is_422_and_changes_nothing(api: Api) -> None:
    """Scenario: 8자 미만으로 재설정하면 422이고 기존 비밀번호로 계속 로그인된다."""
    # Given
    user_id = await given_local_user_registered(api, login_id="kim")
    # When
    response = await when_reset_password(api, user_id, "short7!")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert (await when_log_in_local(api, "kim")).status_code == 200


async def test_admin_edits_name_email_and_phone(api: Api) -> None:
    """Scenario: admin이 이름·이메일·전화를 고치면 목록에 반영되고 아이디·역할은 그대로다."""
    # Given
    user_id = await given_local_user_registered(api, login_id="kim", role="sales")
    # When
    response = await when_patch_user(
        api,
        user_id,
        {"display_name": "김새이름", "email": "New@Corp.test", "phone": "02-123-4567"},
    )
    # Then
    then_status_is(response, 200)
    then_body_includes(
        response,
        login_id="kim",
        role="sales",
        display_name="김새이름",
        email="new@corp.test",
        phone="02-123-4567",
    )
    listed = (await when_list_users(api)).json()["items"]
    row = next(u for u in listed if u["login_id"] == "kim")
    assert (row["display_name"], row["phone"]) == ("김새이름", "02-123-4567")


async def test_admin_edit_with_a_blank_name_is_422(api: Api) -> None:
    """Scenario: local 모드에서 이름을 비우려 하면 422이고 이름은 그대로다."""
    # Given
    user_id = await given_local_user_registered(api, login_id="kim", display_name="김영업")
    # When
    response = await when_patch_user(api, user_id, {"display_name": ""})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    listed = (await when_list_users(api)).json()["items"]
    assert next(u for u in listed if u["login_id"] == "kim")["display_name"] == "김영업"


async def test_admin_edit_of_name_in_ad_mode_is_409_but_phone_is_allowed(api: Api) -> None:
    """Scenario: AD 모드에서 admin이 이름을 고치면 409, 전화는 고칠 수 있다."""
    # Given
    user_id = await given_user_registered(api, login_id="kim", role="sales")
    # When
    name = await when_patch_user(api, user_id, {"display_name": "새 이름"})
    phone = await when_patch_user(api, user_id, {"phone": "02-123-4567"})
    # Then
    then_problem_is(name, status=409, type_suffix="invalid-state")
    then_status_is(phone, 200)
    then_body_includes(phone, phone="02-123-4567")


async def test_user_list_shows_phone_but_no_password(api: Api) -> None:
    """Scenario: 사용자 목록 항목에 phone이 있고 비밀번호·해시는 어디에도 없다."""
    # Given
    await given_local_user_registered(api, login_id="kim", phone="010-1234-5678")
    # When
    response = await when_list_users(api)
    # Then
    then_status_is(response, 200)
    row = next(u for u in response.json()["items"] if u["login_id"] == "kim")
    assert set(row) == USER_KEYS
    assert row["phone"] == "010-1234-5678"
    then_body_has_no_password(response, local_password_of("kim"), local_password_of(ADMIN_LOGIN))


async def test_non_admin_cannot_edit_or_reset_others(api: Api) -> None:
    """Scenario: sales 사용자가 다른 사용자의 정보 수정·비밀번호 재설정을 시도하면 둘 다 403이다."""
    # Given
    other_id = await given_local_user_registered(api, login_id="lee")
    await given_local_user_registered(api, login_id="kim", role="sales")
    await log_in_local(api, "kim")
    # When
    patch = await when_patch_user(api, other_id, {"phone": "02-123-4567"})
    reset = await when_reset_password(api, other_id, "Fresh-passw0rd")
    # Then
    then_problem_is(patch, status=403, type_suffix="forbidden")
    then_problem_is(reset, status=403, type_suffix="forbidden")


async def test_a_reset_user_keeps_other_users_sessions(api: Api) -> None:
    """Scenario: 한 사용자의 비밀번호를 재설정해도 다른 사용자의 로그인은 유지된다."""
    # Given
    kim_id = await given_local_user_registered(api, login_id="kim")
    await given_local_user_registered(api, login_id="lee")
    lee = await given_local_session(api, login_id="lee")
    await log_in_local(api, ADMIN_LOGIN)
    # When
    response = await when_reset_password(api, kim_id, "Fresh-passw0rd")
    # Then
    then_status_is(response, 204)
    await then_session_is_alive(api, lee)
