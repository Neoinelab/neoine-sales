"""내 정보 라우터 (ME-R2~R15): GET·PATCH /me/profile, PUT /me/password.

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
    """local 모드에서 세 역할 모두 자기 정보와 모든 항목 수정 가능 표시를 받는다.

    테스트 코드: ME-001, ME-004
    """
    # given: local 모드이고 해당 역할의 kim(이름 "김영업", 이메일, 전화)으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases, role)
    async with signed_in_as(use_cases, "kim", role) as http:
        # when: GET /me/profile을 부른다
        response = await http.get(MY_PROFILE)

    # then: 200, 키가 정확하고 값·editable이 맞으며 비밀번호 문자열이 없다
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
    """AD 모드 사용자는 전화만 수정 가능하다는 표시를 받는다.

    테스트 코드: ME-002
    """
    # given: AD 모드이고 sales 사용자 kim으로 로그인했다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "kim") as http:
        # when: GET /me/profile을 부른다
        body = (await http.get(MY_PROFILE)).json()

    # then: auth_mode는 ad이고 editable은 전화만 true다
    assert body["auth_mode"] == "ad"
    assert body["editable"] == {
        "display_name": False,
        "email": False,
        "phone": True,
        "password": False,
    }


async def test_profile_without_login_is_401() -> None:
    """로그인하지 않고 내 정보를 조회하면 401이다.

    테스트 코드: ME-005
    """
    # given: 로그인하지 않았다
    async with anonymous(FakeUseCases()) as http:
        # when: GET /me/profile을 부른다
        response = await http.get(MY_PROFILE)

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")


# ---- PATCH /me/profile ----


async def test_user_updates_name_and_me_shows_it() -> None:
    """이름·전화를 고치면 응답과 다음 /auth/me에 새 값이 보인다.

    테스트 코드: ME-006
    """
    # given: local 모드이고 kim(이름 "김영업", 이메일 kim@corp.test)으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 이름과 전화를 PATCH하고 이어서 /auth/me를 부른다
        response = await http.patch(
            MY_PROFILE, json={"display_name": "김새이름", "phone": "010-9999-8888"}
        )
        me = (await http.get(ME)).json()

    # then: 200, 새 이름·전화, 이메일은 그대로이며 /auth/me의 name도 새 이름이다
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
    """보내지 않은 키는 그대로이고 null은 값을 비운다.

    테스트 코드: ME-008
    """
    # given: local 모드이고 kim(이름, 이메일, 전화)으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 이메일만 null로, 이어서 이메일·전화를 null로 보낸다
        first = (await http.patch(MY_PROFILE, json={"email": None})).json()
        second = (await http.patch(MY_PROFILE, json={"email": None, "phone": None})).json()

    # then: 앞은 이메일만 비고 전화는 남으며, 뒤는 이메일·전화가 모두 비고 이름은 그대로다
    assert (first["display_name"], first["email"], first["phone"]) == (
        "김영업",
        None,
        "02-123-4567",
    )
    assert (second["display_name"], second["email"], second["phone"]) == ("김영업", None, None)


async def test_patch_with_an_empty_body_changes_nothing() -> None:
    """빈 본문은 아무것도 바꾸지 않고 현재 정보를 200으로 준다.

    테스트 코드: ME-009
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        before = (await http.get(MY_PROFILE)).json()
        # when: 빈 본문 {}을 PATCH한다
        response = await http.patch(MY_PROFILE, json={})

    # then: 200이고 응답은 직전 조회와 같다
    assert response.status_code == 200, response.text
    assert response.json() == before


@pytest.mark.parametrize("role", list(Role))
async def test_read_only_role_can_edit_own_profile(role: Role) -> None:
    """읽기 전용 user를 포함해 세 역할 모두 자기 정보를 고칠 수 있다(403이 아니다).

    테스트 코드: ME-004
    """
    # given: local 모드이고 해당 역할의 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases, role)
    async with signed_in_as(use_cases, "kim", role) as http:
        # when: 전화를 PATCH한다
        response = await http.patch(MY_PROFILE, json={"phone": "010-1111-2222"})

    # then: 200이고 전화가 바뀐다
    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "010-1111-2222"


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"email": "not-an-email"}, "이메일 형식이 올바르지 않습니다."),
        ({"email": "abc"}, "이메일 형식이 올바르지 않습니다."),
        ({"phone": "12"}, "전화번호 형식이 올바르지 않습니다."),
    ],
)
async def test_invalid_email_or_phone_is_422_invalid_value_and_changes_nothing(
    body: dict[str, Any], detail: str
) -> None:
    """형식이 틀린 이메일·전화는 422 invalid-value이고 값이 바뀌지 않는다.

    테스트 코드: ME-010
    """
    # given: local 모드이고 kim(이메일 kim@corp.test)으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 틀린 이메일 또는 전화를 PATCH한다
        response = await http.patch(MY_PROFILE, json=body)
        after = (await http.get(MY_PROFILE)).json()

    # then: 422 invalid-value와 문구이고 이메일·이름은 그대로다
    assert problem(response, 422, "invalid-value")["detail"] == detail
    assert (after["email"], after["display_name"]) == ("kim@corp.test", "김영업")


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"display_name": ""}, "이름은(는) 비어 있을 수 없습니다"),
        ({"display_name": " "}, "이름은(는) 비어 있을 수 없습니다"),
        ({"display_name": None}, "이름은(는) 비어 있을 수 없습니다"),
        ({"display_name": "가" * 201}, "이름은(는) 200자를 넘을 수 없습니다"),
    ],
)
async def test_blank_or_too_long_name_is_422_invalid_value_and_changes_nothing(
    body: dict[str, Any], detail: str
) -> None:
    """local 모드에서 이름을 비우거나 200자를 넘기면 422 invalid-value다.

    테스트 코드: ME-011
    """
    # given: local 모드이고 kim(이름 "김영업")으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 빈 이름 또는 201자 이름을 PATCH한다
        response = await http.patch(MY_PROFILE, json=body)
        after = (await http.get(MY_PROFILE)).json()

    # then: 422 invalid-value와 문구이고 이름은 "김영업" 그대로다
    assert problem(response, 422, "invalid-value")["detail"] == detail
    assert after["display_name"] == "김영업"


@pytest.mark.parametrize(
    "body",
    [
        {"login_id": "x"},
        {"role": "admin"},
        {"id": 1},
        {"password": "x"},
        {"unknown": 1},
        {"login_id": "other", "role": "admin"},
    ],
)
async def test_extra_keys_such_as_login_id_or_role_are_422_request_validation(
    body: dict[str, Any],
) -> None:
    """본문에 login_id·role 등 다른 키가 있으면 422 request-validation이다.

    테스트 코드: ME-012
    """
    # given: local 모드이고 sales 사용자 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 허용되지 않은 키가 있는 본문을 PATCH한다
        response = await http.patch(MY_PROFILE, json=body)
        after = (await http.get(MY_PROFILE)).json()

    # then: 422 request-validation이고 아이디·역할은 kim·sales 그대로다
    problem(response, 422, "request-validation")
    assert (after["login_id"], after["role"]) == ("kim", "sales")


@pytest.mark.parametrize(
    "body", [{"display_name": "새 이름"}, {"email": "a@b.co"}, {"email": "abc"}]
)
async def test_ad_user_name_or_email_edit_is_409(body: dict[str, Any]) -> None:
    """AD 모드에서 이름·이메일을 고치려 하면 409 invalid-state다(형식이 틀려도 409).

    테스트 코드: ME-013
    """
    # given: AD 모드이고 kim(이름 "김영업")으로 로그인했다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "kim") as http:
        # when: 이름 또는 이메일을 PATCH한다
        response = await http.patch(MY_PROFILE, json=body)
        after = (await http.get(MY_PROFILE)).json()

    # then: 409 invalid-state와 AD 관리 문구이고 이름·이메일은 그대로다
    result = problem(response, 409, "invalid-state")
    assert result["detail"] == "AD 연동 사용자의 이름·이메일은 AD에서 관리합니다."
    assert (after["display_name"], after["email"]) == ("김영업", None)


async def test_ad_user_can_edit_only_phone() -> None:
    """AD 모드에서도 전화는 고칠 수 있다.

    테스트 코드: ME-014
    """
    # given: AD 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "kim") as http:
        # when: 전화를 PATCH한다
        response = await http.patch(MY_PROFILE, json={"phone": "010-1111-2222"})

    # then: 200이고 phone, auth_mode ad, editable은 전화만 true다
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["phone"], body["auth_mode"]) == ("010-1111-2222", "ad")
    assert body["editable"] == {
        "display_name": False,
        "email": False,
        "phone": True,
        "password": False,
    }


async def test_patch_profile_without_login_is_401() -> None:
    """로그인하지 않고 내 정보를 수정하면 401이다.

    테스트 코드: ME-005
    """
    # given: 로그인하지 않았다
    async with anonymous(FakeUseCases()) as http:
        # when: PATCH /me/profile {}을 부른다
        response = await http.patch(MY_PROFILE, json={})

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")


async def test_profile_values_are_normalized_and_boundaries_are_accepted() -> None:
    """이름·이메일·전화는 정규화해 저장하고 경계값을 받아들인다.

    테스트 코드: ME-016
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 공백·대문자가 섞인 값을 보내고, 따로 200자 이름·공백뿐인 이메일·7자리 전화를 보낸다
        normalized = (
            await http.patch(
                MY_PROFILE,
                json={
                    "display_name": "  김새이름  ",
                    "email": "  Kim@Corp.TEST ",
                    "phone": " 02-123-4567 ",
                },
            )
        ).json()
        boundary = (
            await http.patch(
                MY_PROFILE, json={"display_name": "가" * 200, "email": "   ", "phone": "1234567"}
            )
        ).json()

    # then: 앞은 다듬어진 값, 뒤는 200자 이름 그대로·이메일 null·전화 1234567이다
    assert (normalized["display_name"], normalized["email"], normalized["phone"]) == (
        "김새이름",
        "kim@corp.test",
        "02-123-4567",
    )
    assert (boundary["display_name"], boundary["email"], boundary["phone"]) == (
        "가" * 200,
        None,
        "1234567",
    )


# ---- PUT /me/password ----


def _body(current: str = PASSWORD, new: str = "Fresh-passw0rd") -> dict[str, str]:
    return {"current_password": current, "new_password": new}


async def test_changing_password_is_204_and_the_new_password_signs_in() -> None:
    """비밀번호를 바꾸면 204이고 새 비밀번호로만 로그인된다.

    테스트 코드: ME-017
    """
    # given: local 모드이고 kim(현재 비밀번호 PASSWORD)으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 새 비밀번호로 PUT /me/password를 보내고 새로 로그인해 본다
        response = await http.put(MY_PASSWORD, json=_body())
        still = await http.get(ME)
    async with anonymous(use_cases) as other:
        new_login = await other.post(LOGIN, json={"login_id": "kim", "password": "Fresh-passw0rd"})
        old_login = await other.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})

    # then: 204 빈 본문, 지금 세션 200, 새 비밀번호 로그인 200, 이전 비밀번호 401이다
    assert response.status_code == 204, response.text
    assert response.content == b""
    assert still.status_code == 200
    assert new_login.status_code == 200
    assert old_login.status_code == 401


async def test_changing_password_ends_other_sessions_only() -> None:
    """비밀번호를 바꾸면 현재 세션은 남고 같은 사용자의 다른 세션만 끝난다.

    테스트 코드: ME-018
    """
    # given: local 모드이고 kim의 세션 둘(현재·다른 하나)이 있다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as current, signed_in_as(use_cases, "kim") as other:
        before = await other.get(ME)
        # when: 현재 세션으로 비밀번호를 바꾼다
        response = await current.put(MY_PASSWORD, json=_body())
        current_after = await current.get(ME)
        other_after = await other.get(ME)

    # then: 현재 세션은 200, 다른 세션은 401 unauthenticated다
    assert before.status_code == 200
    assert response.status_code == 204
    assert current_after.status_code == 200
    problem(other_after, 401, "unauthenticated")


async def test_wrong_current_password_is_422_on_the_current_password_and_counted() -> None:
    """현재 비밀번호가 틀리면 422(위치 current_password)다.

    테스트 코드: ME-020
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 틀린 현재 비밀번호로 변경을 요청한다
        response = await http.put(MY_PASSWORD, json=_body(current="wrong-pass-1"))

    # then: 422 invalid-value, 위치 [current_password], 고정 문구다
    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["current_password"]]
    assert body["detail"] == "현재 비밀번호가 올바르지 않습니다."


async def test_wrong_current_password_keeps_the_session_and_does_not_log_out() -> None:
    """현재 비밀번호가 틀려도 세션은 유지된다(401이 아니다).

    테스트 코드: ME-020
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 틀린 현재 비밀번호로 변경을 요청한 뒤 /auth/me를 부른다
        await http.put(MY_PASSWORD, json=_body(current="wrong-pass-1"))
        me = await http.get(ME)

    # then: 세션이 살아 있어 200이다
    assert me.status_code == 200


async def test_repeated_wrong_current_passwords_lock_with_429() -> None:
    """실패 한도를 넘으면 맞는 현재 비밀번호여도 429다.

    테스트 코드: ME-021
    """
    # given: local 모드이고 kim이 현재 비밀번호를 계정 한도만큼 틀렸다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        for _ in range(MAX_PER_ACCOUNT):
            await http.put(MY_PASSWORD, json=_body(current="wrong-pass-1"))
        # when: 맞는 현재 비밀번호로 다시 요청한다
        locked = await http.put(MY_PASSWORD, json=_body())

    # then: 429 too-many-attempts다
    problem(locked, 429, "too-many-attempts")


@pytest.mark.parametrize("new", ["short7!", "1234567", "kim"])
async def test_weak_new_password_is_422_on_the_new_password(new: str) -> None:
    """8자 미만 새 비밀번호는 422(위치 new_password)다.

    테스트 코드: ME-024
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 맞는 현재 비밀번호와 8자 미만 새 비밀번호를 보낸다
        response = await http.put(MY_PASSWORD, json=_body(new=new))

    # then: 422 invalid-value, 위치 [new_password], 8자 문구이고 실패 카운터가 없다
    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["new_password"]]
    assert body["detail"] == "비밀번호는 8자 이상이어야 합니다"
    assert use_cases.uow.login_failures._items == {}


@pytest.mark.parametrize("new", ["abcd1234", "x" * 256])
async def test_new_password_of_exactly_the_minimum_or_maximum_length_is_accepted(new: str) -> None:
    """정확히 8자·256자 새 비밀번호는 받아들인다.

    테스트 코드: ME-026
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 경계 길이의 새 비밀번호로 바꾼다
        response = await http.put(MY_PASSWORD, json=_body(new=new))
    async with anonymous(use_cases) as other:
        login = await other.post(LOGIN, json={"login_id": "kim", "password": new})

    # then: 204이고 그 새 비밀번호로 로그인된다
    assert response.status_code == 204, response.text
    assert login.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"current_password": PASSWORD},
        {"new_password": "Fresh-passw0rd"},
        {"current_password": None, "new_password": "Fresh-passw0rd"},
        {"current_password": PASSWORD, "new_password": "x" * 257},
        {"current_password": "x" * 257, "new_password": "Fresh-passw0rd"},
        {"current_password": PASSWORD, "new_password": "Fresh-passw0rd", "extra": 1},
    ],
)
async def test_invalid_password_body_is_422_request_validation(body: dict[str, Any]) -> None:
    """비밀번호 본문 형식 오류는 422 request-validation이다.

    테스트 코드: ME-029
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 키 누락·null·257자·알 수 없는 키가 있는 본문을 보낸다
        response = await http.put(MY_PASSWORD, json=body)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    ("body", "field"),
    [
        (_body(current=""), "current_password"),
        (_body(current="   "), "current_password"),
        (_body(new=""), "new_password"),
    ],
)
async def test_blank_current_or_new_password_is_422_on_that_field(
    body: dict[str, str], field: str
) -> None:
    """빈 현재·새 비밀번호는 422 invalid-value이고 위치가 그 칸이다.

    테스트 코드: ME-030
    """
    # given: local 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 빈(또는 공백뿐인) 비밀번호로 변경을 요청한다
        response = await http.put(MY_PASSWORD, json=body)

    # then: 422 invalid-value, 위치가 그 칸, 비어 있을 수 없다는 문구이며 실패 카운터는 없다
    result = problem(response, 422, "invalid-value")
    assert error_locations(result) == [[field]]
    assert result["detail"] == "비밀번호는 비어 있을 수 없습니다"
    assert use_cases.uow.login_failures._items == {}


async def test_ad_user_cannot_change_the_password() -> None:
    """AD 모드에서 비밀번호를 바꾸려 하면 409 invalid-state다.

    테스트 코드: ME-027
    """
    # given: AD 모드이고 kim으로 로그인했다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("kim", Role.SALES)
    async with signed_in_as(use_cases, "kim") as http:
        # when: 비밀번호 변경을 요청한다
        response = await http.put(MY_PASSWORD, json=_body())

    # then: 409 invalid-state다
    problem(response, 409, "invalid-state")


async def test_change_password_without_login_is_401() -> None:
    """로그인하지 않고 비밀번호를 바꾸면 401이다.

    테스트 코드: ME-005
    """
    # given: 로그인하지 않았다
    async with anonymous(FakeUseCases()) as http:
        # when: PUT /me/password를 부른다
        response = await http.put(MY_PASSWORD, json=_body())

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")


async def test_the_session_token_is_matched_by_the_request_cookie() -> None:
    """유지하는 세션은 요청 쿠키의 세션이다(저장소에는 해시만 있다).

    테스트 코드: ME-019
    """
    # given: local 모드이고 kim의 세션 하나가 쿠키 토큰으로 요청한다
    use_cases = FakeUseCases()
    await _local_kim(use_cases)
    token = await use_cases.login_as(make_principal("kim", Role.SALES))
    async with new_client(use_cases, {SESSION_COOKIE: token}) as http:
        # when: 그 쿠키로 비밀번호를 바꾼다
        await http.put(MY_PASSWORD, json=_body())

    # then: 세션 저장소에 그 토큰의 해시가 남는다
    assert hash_token(token) in use_cases.uow.sessions._items
