"""사용자 관리 라우터의 local 모드 (AC-6·7·8): 등록(비밀번호), 정보 수정(PATCH), 비밀번호 재설정.

모두 admin 전용이다(권한이 본문 검증보다 먼저). 응답·목록에 비밀번호·해시는 없다.
"""

from typing import Any

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.functional.steps.users import USER_KEYS
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


# ---- POST /users (AC-6) ----


async def test_admin_registers_a_local_user_who_can_sign_in() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json=_body(email="Kim@Corp.test", phone="010-1234-5678"))
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
    use_cases = FakeUseCases()
    await _local(use_cases)
    body = _body()
    del body["password"]
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json=body)
        listed = (await admin.get(USERS)).json()["items"]

    problem(response, 422, "invalid-value")
    assert [u["login_id"] for u in listed] == ["root"]


@pytest.mark.parametrize("password", ["short7!", "1234567", "kim"])
async def test_local_registration_with_a_weak_password_is_422_on_the_password(
    password: str,
) -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json=_body(password=password))

    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["password"]]


@pytest.mark.parametrize("name", [None, "", "  "])
async def test_local_registration_without_a_display_name_is_422(name: str | None) -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json=_body(display_name=name))

    problem(response, 422, "invalid-value")


async def test_ad_registration_with_a_password_is_422() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json=_body())
        listed = (await admin.get(USERS)).json()["items"]

    problem(response, 422, "invalid-value")
    assert [u["login_id"] for u in listed] == ["root"]


async def test_ad_registration_accepts_phone_and_email_without_a_password() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    body = {"login_id": "kim", "role": "sales", "phone": "010-1234-5678", "email": "k@corp.test"}
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json=body)

    assert response.status_code == 201, response.text
    assert (response.json()["phone"], response.json()["email"]) == ("010-1234-5678", "k@corp.test")


async def test_the_existing_registration_body_still_works_in_a_legacy_system() -> None:
    use_cases = FakeUseCases()
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json={"login_id": "kim", "role": "sales"})

    assert response.status_code == 201, response.text
    assert response.json()["phone"] is None


async def test_registration_password_must_be_a_string() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.post(USERS, json=_body(password=12345678))

    problem(response, 422, "request-validation")


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_non_admins_cannot_register_local_users(role: Role) -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "worker", role) as http:
        response = await http.post(USERS, json=_body())

    problem(response, 403, "forbidden")


# ---- PATCH /users/{id} (AC-8) ----


def _url(user_id: object) -> str:
    return f"{USERS}/{user_id}"


async def test_admin_edits_name_email_and_phone() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(
            _url(kim.id),
            json={"display_name": "이영업", "email": "Lee@Corp.test", "phone": "02-123-4567"},
        )
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
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user(
        "kim", PASSWORD, display_name="김영업", email="kim@corp.test", phone="02-123-4567"
    )
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(kim.id), json={"email": None})

    body = response.json()
    assert (body["display_name"], body["email"], body["phone"]) == ("김영업", None, "02-123-4567")


async def test_patch_with_an_empty_body_changes_nothing() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(kim.id), json={})

    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "김영업"


@pytest.mark.parametrize(
    "body",
    [{"display_name": ""}, {"display_name": None}, {"email": "abc"}, {"phone": "12"}],
)
async def test_patch_invalid_values_are_422_invalid_value(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(kim.id), json=body)

    problem(response, 422, "invalid-value")


@pytest.mark.parametrize(
    "body", [{"login_id": "x"}, {"role": "admin"}, {"password": "x"}, {"id": 1}]
)
async def test_patch_cannot_carry_login_id_role_or_password(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(kim.id), json=body)

    problem(response, 422, "request-validation")


@pytest.mark.parametrize("body", [{"display_name": "새 이름"}, {"email": "a@b.co"}])
async def test_patch_name_or_email_in_ad_mode_is_409(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    kim = await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(kim.id), json=body)

    problem(response, 409, "invalid-state")


async def test_patch_phone_in_ad_mode_is_allowed() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(kim.id), json={"phone": "02-123-4567"})

    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "02-123-4567"


async def test_patch_a_resigned_user_is_409() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    gone = await use_cases.seed_local_user("gone", PASSWORD)
    await use_cases.resign_user(gone.id)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(gone.id), json={"phone": "02-123-4567"})

    problem(response, 409, "invalid-state")


async def test_patch_an_unknown_user_is_404() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(MISSING_ID), json={"phone": "02-123-4567"})

    problem(response, 404, "not-found")


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "-1", "0"])
async def test_patch_a_malformed_user_id_is_422(bad_id: str) -> None:
    async with signed_in_as(FakeUseCases(), "root", Role.ADMIN) as admin:
        response = await admin.patch(_url(bad_id), json={})

    problem(response, 422, "request-validation")


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_patch_by_non_admins_is_403_before_body_validation(role: Role) -> None:
    async with signed_in_as(FakeUseCases(), "worker", role) as http:
        response = await http.patch(_url(MISSING_ID), json={"unexpected": 1})

    problem(response, 403, "forbidden")


async def test_patch_without_login_is_401() -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.patch(_url(MISSING_ID), json={})

    problem(response, 401, "unauthenticated")


# ---- PUT /users/{id}/password (AC-7) ----


def _pw_url(user_id: object) -> str:
    return f"{USERS}/{user_id}/password"


async def test_admin_resets_a_password_ends_sessions_and_the_new_password_works() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD)
    async with signed_in_as(use_cases, "kim") as kim_http:
        assert (await kim_http.get(ME)).status_code == 200
        async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
            response = await admin.put(_pw_url(kim.id), json={"password": "Fresh-passw0rd"})
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
    use_cases = FakeUseCases()
    await _local(use_cases)
    root = await use_cases.seed_local_user("root", PASSWORD, Role.ADMIN)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.put(_pw_url(root.id), json={"password": "Fresh-passw0rd"})

    problem(response, 409, "invalid-state")


async def test_reset_password_in_ad_mode_is_409() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.put(_pw_url(kim.id), json={"password": "Fresh-passw0rd"})

    problem(response, 409, "invalid-state")


async def test_reset_password_of_a_resigned_user_is_409() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    gone = await use_cases.seed_local_user("gone", PASSWORD)
    await use_cases.resign_user(gone.id)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.put(_pw_url(gone.id), json={"password": "Fresh-passw0rd"})

    problem(response, 409, "invalid-state")


@pytest.mark.parametrize("password", ["short7!", "1234567", "kim"])
async def test_reset_password_weak_is_422_on_the_password_field(password: str) -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.put(_pw_url(kim.id), json={"password": password})

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
    use_cases = FakeUseCases()
    await _local(use_cases)
    kim = await use_cases.seed_local_user("kim", PASSWORD)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.put(_pw_url(kim.id), json=body)

    problem(response, 422, "request-validation")


async def test_reset_password_of_an_unknown_user_is_404() -> None:
    use_cases = FakeUseCases()
    await _local(use_cases)
    async with signed_in_as(use_cases, "root", Role.ADMIN) as admin:
        response = await admin.put(_pw_url(MISSING_ID), json={"password": "Fresh-passw0rd"})

    problem(response, 404, "not-found")


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_reset_password_by_non_admins_is_403_before_body_validation(role: Role) -> None:
    async with signed_in_as(FakeUseCases(), "worker", role) as http:
        response = await http.put(_pw_url(MISSING_ID), json={"unexpected": 1})

    problem(response, 403, "forbidden")


async def test_reset_password_without_login_is_401() -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.put(_pw_url(MISSING_ID), json={"password": PASSWORD})

    problem(response, 401, "unauthenticated")
