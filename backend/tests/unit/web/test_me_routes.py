"""내 정보 라우터 (AC-9·10·11): GET·PATCH /me/profile, PUT /me/password.

로그인한 모든 역할이 쓴다. 아이디·역할은 바꿀 수 없다(본문에 있으면 422 request-validation).
현재 비밀번호 확인 실패는 401이 아니라 422 invalid-value(위치 current_password)다.
"""

from typing import Any

import pytest

from app.application.auth.tokens import hash_token
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.factories_auth import make_principal
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.local_account_http import (
    LOGIN,
    ME,
    MY_PASSWORD,
    MY_PROFILE,
    PASSWORD,
    SESSION_COOKIE,
    anonymous,
    error_locations,
    new_client,
    problem,
    signed_in_as,
)

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
EDITABLE_KEYS = {"display_name", "email", "phone", "password"}


async def _local_kim(use_cases: FakeUseCases, role: Role = Role.SALES) -> None:
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    await use_cases.seed_local_user(
        "kim", PASSWORD, role, display_name="김영업", email="kim@corp.test", phone="02-123-4567"
    )


# ---- GET /me/profile ----


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_sees_its_own_profile_with_editable_flags(role: Role) -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases, role)
    async with signed_in_as(use_cases, "kim", role) as http:
        response = await http.get(MY_PROFILE)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == PROFILE_KEYS
    assert set(body["editable"]) == EDITABLE_KEYS
    assert (body["login_id"], body["role"], body["display_name"]) == ("kim", role.value, "김영업")
    assert (body["email"], body["phone"], body["auth_mode"]) == (
        "kim@corp.test",
        "02-123-4567",
        "local",
    )
    assert type(body["id"]) is int
    assert body["editable"] == {
        "display_name": True,
        "email": True,
        "phone": True,
        "password": True,
    }
    assert PASSWORD not in response.text


async def test_ad_user_profile_flags_allow_only_the_phone() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "kim") as http:
        body = (await http.get(MY_PROFILE)).json()

    assert body["auth_mode"] == "ad"
    assert body["editable"] == {
        "display_name": False,
        "email": False,
        "phone": True,
        "password": False,
    }


async def test_dev_user_profile_cannot_change_the_password() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    async with signed_in_as(use_cases, "dev-sales") as http:
        body = (await http.get(MY_PROFILE)).json()

    assert body["editable"]["password"] is False
    assert body["editable"]["display_name"] is True


async def test_profile_without_login_is_401() -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.get(MY_PROFILE)

    problem(response, 401, "unauthenticated")


# ---- PATCH /me/profile ----


async def test_user_updates_name_and_me_shows_it() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.patch(
            MY_PROFILE, json={"display_name": "김새이름", "phone": "010-9999-8888"}
        )
        me = (await http.get(ME)).json()

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == PROFILE_KEYS
    assert (body["display_name"], body["phone"], body["email"]) == (
        "김새이름",
        "010-9999-8888",
        "kim@corp.test",
    )
    assert me["name"] == "김새이름"


async def test_patch_null_clears_email_and_phone_and_omitted_keys_stay() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        body = (await http.patch(MY_PROFILE, json={"email": None, "phone": None})).json()

    assert (body["display_name"], body["email"], body["phone"]) == ("김영업", None, None)


async def test_patch_with_an_empty_body_changes_nothing() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        before = (await http.get(MY_PROFILE)).json()
        response = await http.patch(MY_PROFILE, json={})

    assert response.status_code == 200, response.text
    assert response.json() == before


@pytest.mark.parametrize("role", list(Role))
async def test_read_only_role_can_edit_own_profile(role: Role) -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases, role)
    async with signed_in_as(use_cases, "kim", role) as http:
        response = await http.patch(MY_PROFILE, json={"phone": "010-1111-2222"})

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "body",
    [
        {"email": "abc"},
        {"phone": "12"},
        {"display_name": ""},
        {"display_name": None},
        {"display_name": "가" * 201},
    ],
)
async def test_invalid_values_are_422_invalid_value(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.patch(MY_PROFILE, json=body)
        after = (await http.get(MY_PROFILE)).json()

    problem(response, 422, "invalid-value")
    assert after["display_name"] == "김영업"


@pytest.mark.parametrize(
    "body",
    [{"login_id": "x"}, {"role": "admin"}, {"id": 1}, {"password": "x"}, {"unknown": 1}],
)
async def test_extra_keys_such_as_login_id_or_role_are_422_request_validation(
    body: dict[str, Any],
) -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.patch(MY_PROFILE, json=body)
        after = (await http.get(MY_PROFILE)).json()

    problem(response, 422, "request-validation")
    assert (after["login_id"], after["role"]) == ("kim", "sales")


@pytest.mark.parametrize("body", [{"display_name": "새 이름"}, {"email": "a@b.co"}])
async def test_ad_user_name_or_email_edit_is_409(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.patch(MY_PROFILE, json=body)

    problem(response, 409, "invalid-state")


async def test_ad_user_can_edit_only_phone() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.patch(MY_PROFILE, json={"phone": "010-1111-2222"})

    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "010-1111-2222"


async def test_patch_profile_without_login_is_401() -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.patch(MY_PROFILE, json={})

    problem(response, 401, "unauthenticated")


# ---- PUT /me/password ----


def _body(current: str = PASSWORD, new: str = "Fresh-passw0rd") -> dict[str, str]:
    return {"current_password": current, "new_password": new}


async def test_changing_password_is_204_and_the_new_password_signs_in() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.put(MY_PASSWORD, json=_body())
        still = await http.get(ME)
    async with anonymous(use_cases) as other:
        new_login = await other.post(LOGIN, json={"login_id": "kim", "password": "Fresh-passw0rd"})
        old_login = await other.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})

    assert response.status_code == 204, response.text
    assert response.content == b""
    assert still.status_code == 200
    assert new_login.status_code == 200
    assert old_login.status_code == 401


async def test_changing_password_ends_other_sessions_only() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as current, signed_in_as(use_cases, "kim") as other:
        before = await other.get(ME)
        response = await current.put(MY_PASSWORD, json=_body())
        current_after = await current.get(ME)
        other_after = await other.get(ME)

    assert before.status_code == 200
    assert response.status_code == 204
    assert current_after.status_code == 200
    problem(other_after, 401, "unauthenticated")


async def test_wrong_current_password_is_422_on_the_current_password_and_counted() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.put(MY_PASSWORD, json=_body(current="wrong-pass-1"))

    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["current_password"]]
    assert body["detail"] == "현재 비밀번호가 올바르지 않습니다."


async def test_wrong_current_password_keeps_the_session_and_does_not_log_out() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        await http.put(MY_PASSWORD, json=_body(current="wrong-pass-1"))
        me = await http.get(ME)

    assert me.status_code == 200


async def test_repeated_wrong_current_passwords_lock_with_429() -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        for _ in range(MAX_PER_ACCOUNT):
            await http.put(MY_PASSWORD, json=_body(current="wrong-pass-1"))
        locked = await http.put(MY_PASSWORD, json=_body())

    problem(locked, 429, "too-many-attempts")


@pytest.mark.parametrize("new", ["short7!", "1234567", "kim"])
async def test_weak_new_password_is_422_on_the_new_password(new: str) -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.put(MY_PASSWORD, json=_body(new=new))

    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["new_password"]]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"current_password": PASSWORD},
        {"new_password": "Fresh-passw0rd"},
        {"current_password": None, "new_password": "Fresh-passw0rd"},
        {"current_password": PASSWORD, "new_password": "x" * 257},
        {"current_password": PASSWORD, "new_password": "Fresh-passw0rd", "extra": 1},
    ],
)
async def test_invalid_password_body_is_422_request_validation(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.put(MY_PASSWORD, json=body)

    problem(response, 422, "request-validation")


async def test_ad_user_cannot_change_the_password() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES)
    async with signed_in_as(use_cases, "kim") as http:
        response = await http.put(MY_PASSWORD, json=_body())

    problem(response, 409, "invalid-state")


async def test_dev_user_cannot_change_the_password() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    async with signed_in_as(use_cases, "dev-sales") as http:
        response = await http.put(MY_PASSWORD, json=_body())

    problem(response, 409, "invalid-state")


async def test_change_password_without_login_is_401() -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.put(MY_PASSWORD, json=_body())

    problem(response, 401, "unauthenticated")


async def test_the_session_token_is_matched_by_the_request_cookie() -> None:
    """현재 세션은 요청 쿠키의 토큰으로 정한다(저장소에는 해시만 있다)."""
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    token = await use_cases.login_as(make_principal("kim", Role.SALES))
    async with new_client(use_cases, {SESSION_COOKIE: token}) as http:
        await http.put(MY_PASSWORD, json=_body())

    assert hash_token(token) in use_cases.uow.sessions._items
