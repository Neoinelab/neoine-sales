"""Feature: 로그인한 사용자는 아이디를 뺀 자기 정보(이름·이메일·전화)를 보고 고친다.

local 모드는 이름(비울 수 없음)·이메일·전화와 비밀번호 변경, AD 모드는 전화만 고칠 수 있다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.local_accounts import (
    given_ad_system_with_user,
    given_local_user_signed_in,
    then_body_has_no_password,
    when_get_me,
    when_get_my_profile,
    when_patch_my_profile,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

PROFILE_KEYS = {
    "id",
    "login_id",
    "role",
    "display_name",
    "email",
    "phone",
    "auth_mode",
    "editable",
}


async def test_user_sees_own_profile_with_editable_flags(api: Api) -> None:
    """Scenario: local 사용자가 내 정보를 보면 자기 값과 항목별 수정 가능 여부를 받는다."""
    # Given
    user_id = await given_local_user_signed_in(
        api, login_id="kim", role="sales", email="kim@corp.test", phone="02-123-4567"
    )
    # When
    response = await when_get_my_profile(api)
    # Then
    then_status_is(response, 200)
    assert set(response.json()) == PROFILE_KEYS
    then_body_includes(
        response,
        id=user_id,
        login_id="kim",
        role="sales",
        display_name="사용자 kim",
        email="kim@corp.test",
        phone="02-123-4567",
        auth_mode="local",
        editable={"display_name": True, "email": True, "phone": True, "password": True},
    )
    then_body_has_no_password(response)


async def test_user_updates_name_and_me_shows_it(api: Api) -> None:
    """Scenario: 이름을 고치면 응답에 반영되고 바로 다음 /auth/me에도 새 이름이 보인다."""
    # Given
    await given_local_user_signed_in(api, login_id="kim")
    # When
    response = await when_patch_my_profile(
        api, {"display_name": "김새이름", "phone": "010-9999-8888"}
    )
    # Then
    then_status_is(response, 200)
    then_body_includes(response, display_name="김새이름", phone="010-9999-8888")
    then_body_includes(await when_get_me(api), name="김새이름")


async def test_omitted_keys_stay_and_null_clears(api: Api) -> None:
    """Scenario: 보내지 않은 항목은 그대로이고 null을 보낸 항목은 비워진다."""
    # Given
    await given_local_user_signed_in(
        api, login_id="kim", email="kim@corp.test", phone="02-123-4567"
    )
    # When
    response = await when_patch_my_profile(api, {"email": None})
    # Then
    then_status_is(response, 200)
    then_body_includes(response, display_name="사용자 kim", email=None, phone="02-123-4567")


async def test_invalid_email_is_422(api: Api) -> None:
    """Scenario: 형식이 틀린 이메일은 422(invalid-value)이고 값은 바뀌지 않는다."""
    # Given
    await given_local_user_signed_in(api, login_id="kim", email="kim@corp.test")
    # When
    response = await when_patch_my_profile(api, {"email": "not-an-email"})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_body_includes(await when_get_my_profile(api), email="kim@corp.test")


async def test_login_id_in_body_is_422(api: Api) -> None:
    """Scenario: 본문에 login_id나 role이 있으면 422이고 아이디·역할은 그대로다."""
    # Given
    await given_local_user_signed_in(api, login_id="kim", role="sales")
    # When
    response = await when_patch_my_profile(api, {"login_id": "other", "role": "admin"})
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    then_body_includes(await when_get_my_profile(api), login_id="kim", role="sales")


async def test_local_user_cannot_blank_the_name(api: Api) -> None:
    """Scenario: local 사용자가 이름을 비우려 하면 422이고 이름은 그대로다."""
    # Given
    await given_local_user_signed_in(api, login_id="kim")
    # When
    response = await when_patch_my_profile(api, {"display_name": ""})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_body_includes(await when_get_my_profile(api), display_name="사용자 kim")


async def test_ad_user_can_edit_only_phone(api: Api) -> None:
    """Scenario: AD 사용자는 전화만 고칠 수 있고 이름·이메일은 409(AD에서 관리)다."""
    # Given
    await given_ad_system_with_user(api, login_id="kim", display_name="김영업")
    # When
    phone = await when_patch_my_profile(api, {"phone": "010-1111-2222"})
    name = await when_patch_my_profile(api, {"display_name": "새 이름"})
    # Then
    then_status_is(phone, 200)
    then_body_includes(
        phone,
        auth_mode="ad",
        phone="010-1111-2222",
        editable={"display_name": False, "email": False, "phone": True, "password": False},
    )
    then_problem_is(name, status=409, type_suffix="invalid-state")


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_including_read_only_can_edit_own_profile(api: Api, role: str) -> None:
    """Scenario: 조회 전용(user)을 포함한 모든 역할이 자기 정보를 고칠 수 있다."""
    # Given
    await given_local_user_signed_in(api, login_id="kim", role=role)  # type: ignore[arg-type]
    # When
    response = await when_patch_my_profile(api, {"phone": "010-1111-2222"})
    # Then
    then_status_is(response, 200)
    then_body_includes(response, role=role, phone="010-1111-2222")
