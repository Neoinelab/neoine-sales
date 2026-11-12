"""사용자 관리 라우터의 local 모드: 등록(비밀번호), 정보 수정(PATCH), 비밀번호 재설정.

모두 admin 전용이다(권한이 본문 검증보다 먼저). 응답·목록에 비밀번호·해시는 없다.
"""

from typing import Any

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import USER_KEYS
from tests.support.ids import MISSING_ID
from tests.unit.web.local_account_http import (
    LOGIN,
    ME,
    PASSWORD,
    USERS,
    anonymous,
    error_locations,
    problem,
    signed_in_as,
)


def _body(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "login_id": "kim",
        "role": "sales",
        "display_name": "김영업",
        "password": PASSWORD,
        **overrides,
    }


async def _local(use_cases: FakeUseCases) -> None:
    await use_cases.seed_auth_mode(AuthMode.LOCAL)


# ---- POST /users ----


async def test_admin_registers_a_local_user_who_can_sign_in() -> None:
    """local 모드에서 admin이 등록한 사용자는 그 비밀번호로 로그인된다

    테스트 코드: US-017
    """
    # given: local 모드, admin 로그인
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 비밀번호·이름·이메일·전화로 등록한다
        response = await admin.post(USERS, json=_body(email="Kim@Corp.test", phone="010-1234-5678"))
        # then: 201과 프로필이 돌아오고 비밀번호는 응답에 없으며 그 비밀번호로 로그인된다
        listed = (await admin.get(USERS)).json()["items"]
    async with anonymous(use_cases) as http:
        login = await http.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == USER_KEYS
    assert (body["login_id"], body["display_name"], body["email"], body["phone"]) == (
        "kim",
        "김영업",
        "kim@corp.test",
        "010-1234-5678",
    )
    assert PASSWORD not in response.text
    assert next(u for u in listed if u["login_id"] == "kim")["phone"] == "010-1234-5678"
    assert login.status_code == 200, login.text


async def test_local_registration_without_a_password_is_422() -> None:
    """local 모드에서 비밀번호 없이 등록하면 422이다

    테스트 코드: US-018
    """
    # given: local 모드, admin 로그인
    use_cases = FakeUseCases()
    await _local(use_cases)
    body = _body()
    del body["password"]
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 비밀번호 없이 등록한다
        response = await admin.post(USERS, json=body)
        # then: 422 invalid-value이고 목록에 새 사용자가 없다
        listed = (await admin.get(USERS)).json()["items"]

    problem(response, 422, "invalid-value")
    assert [u["login_id"] for u in listed] == ["root"]


@pytest.mark.parametrize("password", ["short7!", "1234567", "kim"])
async def test_local_registration_with_a_weak_password_is_422_on_the_password(
    password: str,
) -> None:
    """약한 비밀번호는 422이고 오류 위치가 password다

    테스트 코드: US-020
    """
    # given: local 모드, admin 로그인
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 약한 비밀번호로 등록한다
        response = await admin.post(USERS, json=_body(password=password))

    # then: 422 invalid-value이고 위치가 password다
    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["password"]]


@pytest.mark.parametrize("name", [None, "", "  "])
async def test_local_registration_without_a_display_name_is_422(name: str | None) -> None:
    """local 모드에서 이름이 없거나 비면 422이다

    테스트 코드: US-019
    """
    # given: local 모드, admin 로그인
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 이름 없이 등록한다
        response = await admin.post(USERS, json=_body(display_name=name))

    # then: 422 invalid-value다
    problem(response, 422, "invalid-value")


async def test_ad_registration_with_a_password_is_422() -> None:
    """AD 모드에서 비밀번호를 보내면 422 invalid-value이고 저장되지 않는다

    테스트 코드: US-011
    """
    # given: AD 모드, admin 로그인
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 비밀번호와 함께 등록한다
        response = await admin.post(USERS, json=_body())
        # then: 422 invalid-value이고 목록에 새 사용자가 없다
        listed = (await admin.get(USERS)).json()["items"]

    problem(response, 422, "invalid-value")
    assert [u["login_id"] for u in listed] == ["root"]


async def test_ad_registration_accepts_phone_and_email_without_a_password() -> None:
    """AD 모드는 비밀번호 없이 이메일·전화만 주고 등록할 수 있다"""
    # given: AD 모드, admin 로그인
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    body = {"login_id": "kim", "role": "sales", "phone": "010-1234-5678", "email": "k@corp.test"}
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 이메일·전화만 주고 등록한다
        response = await admin.post(USERS, json=body)

    # then: 201이고 이메일·전화가 저장된다
    assert response.status_code == 201, response.text
    assert (response.json()["phone"], response.json()["email"]) == ("010-1234-5678", "k@corp.test")


async def test_the_existing_registration_body_still_works_in_a_legacy_system() -> None:
    """방식 행이 없는 기존 시스템에서도 아이디·역할만으로 등록된다"""
    # given: 방식 행이 없는 시스템
    use_cases = FakeUseCases()
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 아이디·역할만으로 등록한다
        response = await admin.post(USERS, json={"login_id": "kim", "role": "sales"})

    # then: 201이고 전화는 null이다
    assert response.status_code == 201, response.text
    assert response.json()["phone"] is None


async def test_registration_password_must_be_a_string() -> None:
    """비밀번호가 문자열이 아니면 request-validation 422이다

    테스트 코드: US-016
    """
    # given: local 모드, admin 로그인
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 숫자 비밀번호로 등록한다
        response = await admin.post(USERS, json=_body(password=12345678))

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_non_admins_cannot_register_local_users(role: Role) -> None:
    """admin이 아니면 사용자 등록은 403이다

    테스트 코드: US-075
    """
    # given: local 모드, sales 또는 user 로그인
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "worker", role) as http:
        # when: 사용자를 등록한다
        response = await http.post(USERS, json=_body())

    # then: 403 forbidden이다
    problem(response, 403, "forbidden")


# ---- PATCH /users/{id} ----


def _url(user_id: object) -> str:
    return f"{USERS}/{user_id}"


async def test_admin_edits_name_email_and_phone() -> None:
    """admin이 이름·이메일·전화를 고치면 응답과 목록에 반영되고 아이디·역할은 그대로다

    테스트 코드: US-040
    """
    # given: local 모드, kim
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 이름·이메일·전화를 PATCH한다
        response = await admin.patch(
            _url(kim.id),
            json={"display_name": "이영업", "email": "Lee@Corp.test", "phone": "02-123-4567"},
        )
        # then: 200과 정규화된 값이고 목록에도 반영되며 아이디·역할은 그대로다
        listed = (await admin.get(USERS)).json()["items"]

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == USER_KEYS
    assert (body["display_name"], body["email"], body["phone"]) == (
        "이영업",
        "lee@corp.test",
        "02-123-4567",
    )
    row = next(u for u in listed if u["login_id"] == "kim")
    assert (row["display_name"], row["phone"]) == ("이영업", "02-123-4567")
    assert (body["login_id"], body["role"]) == ("kim", "sales")


async def test_patch_omitted_keys_are_kept_and_null_clears() -> None:
    """보내지 않은 키는 그대로이고 null은 그 칸을 비운다

    테스트 코드: US-041
    """
    # given: local 모드, 프로필이 있는 kim
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user(
        "kim", PASSWORD, display_name="김영업", email="kim@corp.test", phone="02-123-4567"
    )
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 이메일만 null로 PATCH한다
        response = await admin.patch(_url(kim.id), json={"email": None})

    # then: 이메일만 null이고 나머지는 그대로다
    body = response.json()
    assert (body["display_name"], body["email"], body["phone"]) == ("김영업", None, "02-123-4567")


async def test_patch_with_an_empty_body_changes_nothing() -> None:
    """빈 본문 PATCH는 200이고 아무것도 바꾸지 않는다

    테스트 코드: US-042
    """
    # given: local 모드, kim
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 빈 본문으로 PATCH한다
        response = await admin.patch(_url(kim.id), json={})

    # then: 200이고 이름이 그대로다
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "김영업"


@pytest.mark.parametrize(
    "body",
    [{"display_name": ""}, {"display_name": None}, {"email": "abc"}, {"phone": "12"}],
)
async def test_patch_invalid_values_are_422_invalid_value(body: dict[str, Any]) -> None:
    """이름을 비우거나 형식이 틀린 이메일·전화는 422 invalid-value이다

    테스트 코드: US-043, US-044
    """
    # given: local 모드, kim
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 잘못된 값으로 PATCH한다
        response = await admin.patch(_url(kim.id), json=body)

    # then: 422 invalid-value다
    problem(response, 422, "invalid-value")


@pytest.mark.parametrize(
    "body", [{"login_id": "x"}, {"role": "admin"}, {"password": "x"}, {"id": 1}]
)
async def test_patch_cannot_carry_login_id_role_or_password(body: dict[str, Any]) -> None:
    """정보 수정 본문에 아이디·역할·비밀번호를 보내면 422이다

    테스트 코드: US-048
    """
    # given: local 모드, kim
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 아이디·역할·비밀번호·id 키를 보낸다
        response = await admin.patch(_url(kim.id), json=body)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("body", [{"display_name": "새 이름"}, {"email": "a@b.co"}])
async def test_patch_name_or_email_in_ad_mode_is_409(body: dict[str, Any]) -> None:
    """AD 모드에서 이름·이메일 수정은 409이다

    테스트 코드: US-045
    """
    # given: AD 모드, kim
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    kim = await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 이름 또는 이메일을 PATCH한다
        response = await admin.patch(_url(kim.id), json=body)

    # then: 409 invalid-state다
    problem(response, 409, "invalid-state")


async def test_patch_phone_in_ad_mode_is_allowed() -> None:
    """AD 모드에서도 전화는 고칠 수 있다

    테스트 코드: US-045
    """
    # given: AD 모드, kim
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 전화를 PATCH한다
        response = await admin.patch(_url(kim.id), json={"phone": "02-123-4567"})

    # then: 200이고 전화가 바뀐다
    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "02-123-4567"


async def test_patch_a_resigned_user_is_409() -> None:
    """퇴사자의 정보 수정은 409이다

    테스트 코드: US-046
    """
    # given: local 모드, 퇴사한 사용자
    use_cases = FakeUseCases()
    await _local(use_cases)
    gone = await use_cases.seed_local_user("gone", PASSWORD)
    await use_cases.resign_user(gone.id)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 전화를 PATCH한다
        response = await admin.patch(_url(gone.id), json={"phone": "02-123-4567"})

    # then: 409 invalid-state다
    problem(response, 409, "invalid-state")


async def test_patch_an_unknown_user_is_404() -> None:
    """없는 사용자의 정보 수정은 404이다

    테스트 코드: US-047
    """
    # given: local 모드
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 없는 id를 PATCH한다
        response = await admin.patch(_url(MISSING_ID), json={"phone": "02-123-4567"})

    # then: 404 not-found다
    problem(response, 404, "not-found")


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "-1", "0"])
async def test_patch_a_malformed_user_id_is_422(bad_id: str) -> None:
    """정보 수정의 id 형식이 틀리면 422이다"""
    # given: admin 로그인
    async with signed_in_as(FakeUseCases(), "root", Role.ADMIN) as admin:
        # when: 잘못된 id로 PATCH한다
        response = await admin.patch(_url(bad_id), json={})

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_patch_by_non_admins_is_403_before_body_validation(role: Role) -> None:
    """admin이 아니면 정보 수정은 본문 검증보다 먼저 403이다

    테스트 코드: US-075
    """
    # given: sales 또는 user 로그인
    async with signed_in_as(FakeUseCases(), "worker", role) as http:
        # when: 잘못된 본문으로 PATCH한다
        response = await http.patch(_url(MISSING_ID), json={"unexpected": 1})

    # then: 403 forbidden이다
    problem(response, 403, "forbidden")


async def test_patch_without_login_is_401() -> None:
    """로그인하지 않은 정보 수정은 401이다"""
    # given: 로그인 없음
    async with anonymous(FakeUseCases()) as http:
        # when: PATCH한다
        response = await http.patch(_url(MISSING_ID), json={})

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")


# ---- PUT /users/{id}/password ----


def _pw_url(user_id: object) -> str:
    return f"{USERS}/{user_id}/password"


async def test_admin_resets_a_password_ends_sessions_and_the_new_password_works() -> None:
    """비밀번호를 재설정하면 204이고 대상의 세션이 끝나며 새 비밀번호로만 로그인된다

    테스트 코드: US-049
    """
    # given: local 모드, 로그인한 kim과 admin
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD)
    async with signed_in_as(use_cases, "kim") as kim_http:
        assert (await kim_http.get(ME)).status_code == 200
        async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
            # when: kim의 비밀번호를 재설정한다
            response = await admin.put(_pw_url(kim.id), json={"password": "Fresh-passw0rd"})
        # then: 204 본문 없음, kim의 기존 세션은 401, 새 비밀번호만 로그인된다
        after = await kim_http.get(ME)
    async with anonymous(use_cases) as http:
        new_login = await http.post(LOGIN, json={"login_id": "kim", "password": "Fresh-passw0rd"})
        old_login = await http.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})

    assert response.status_code == 204, response.text
    assert response.content == b""
    problem(after, 401, "unauthenticated")
    assert new_login.status_code == 200, new_login.text
    assert old_login.status_code == 401


async def test_reset_password_of_self_is_409() -> None:
    """자기 자신의 비밀번호 재설정은 409이다

    테스트 코드: US-053
    """
    # given: local 모드, admin 로그인
    use_cases = FakeUseCases()
    await _local(use_cases)
    root = await use_cases.seed_local_user("root", PASSWORD, Role.ADMIN)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 자기 비밀번호를 재설정한다
        response = await admin.put(_pw_url(root.id), json={"password": "Fresh-passw0rd"})

    # then: 409 invalid-state다
    problem(response, 409, "invalid-state")


async def test_reset_password_in_ad_mode_is_409() -> None:
    """AD 모드에서 재설정은 409이다

    테스트 코드: US-052
    """
    # given: AD 모드, admin 로그인
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 재설정한다
        response = await admin.put(_pw_url(kim.id), json={"password": "Fresh-passw0rd"})

    # then: 409 invalid-state다
    problem(response, 409, "invalid-state")


async def test_reset_password_of_a_resigned_user_is_409() -> None:
    """퇴사자의 재설정은 409이다

    테스트 코드: US-054
    """
    # given: local 모드, 퇴사한 사용자
    use_cases = FakeUseCases()
    await _local(use_cases)
    gone = await use_cases.seed_local_user("gone", PASSWORD)
    await use_cases.resign_user(gone.id)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 재설정한다
        response = await admin.put(_pw_url(gone.id), json={"password": "Fresh-passw0rd"})

    # then: 409 invalid-state다
    problem(response, 409, "invalid-state")


@pytest.mark.parametrize("password", ["short7!", "1234567", "kim"])
async def test_reset_password_weak_is_422_on_the_password_field(password: str) -> None:
    """약한 비밀번호로 재설정하면 422이고 오류 위치가 password다

    테스트 코드: US-055
    """
    # given: local 모드, kim
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 약한 비밀번호로 재설정한다
        response = await admin.put(_pw_url(kim.id), json={"password": password})

    # then: 422 invalid-value이고 위치가 password다
    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["password"]]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"password": None},
        {"password": 12345678},
        {"password": "x" * 257},
        {"password": PASSWORD, "extra": 1},
    ],
)
async def test_reset_password_invalid_body_is_422_request_validation(body: dict[str, Any]) -> None:
    """재설정 본문이 틀리면 request-validation 422이다"""
    # given: local 모드, kim
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 틀린 본문으로 재설정한다
        response = await admin.put(_pw_url(kim.id), json=body)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_reset_password_of_an_unknown_user_is_404() -> None:
    """없는 사용자의 재설정은 404이다

    테스트 코드: US-056
    """
    # given: local 모드
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        # when: 없는 id를 재설정한다
        response = await admin.put(_pw_url(MISSING_ID), json={"password": "Fresh-passw0rd"})

    # then: 404 not-found다
    problem(response, 404, "not-found")


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_reset_password_by_non_admins_is_403_before_body_validation(role: Role) -> None:
    """admin이 아니면 재설정은 본문 검증보다 먼저 403이다

    테스트 코드: US-075
    """
    # given: sales 또는 user 로그인
    async with signed_in_as(FakeUseCases(), "worker", role) as http:
        # when: 잘못된 본문으로 재설정한다
        response = await http.put(_pw_url(MISSING_ID), json={"unexpected": 1})

    # then: 403 forbidden이다
    problem(response, 403, "forbidden")


async def test_reset_password_without_login_is_401() -> None:
    """로그인하지 않은 재설정은 401이다"""
    # given: 로그인 없음
    async with anonymous(FakeUseCases()) as http:
        # when: 재설정한다
        response = await http.put(_pw_url(MISSING_ID), json={"password": PASSWORD})

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")
