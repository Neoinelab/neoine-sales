"""인증 라우터의 local 모드 (AC-1·2·3·4·5): 설정 상태, 인증 방식 선택, 최초 설정, 로그인.

FakeUseCases 위에서 라우터·스키마·오류 매핑을 확인한다. 실제 DB를 지나는 시나리오는 functional
(setup/test_setup_local.py, auth/test_local_login.py)이 맡는다.
"""

from typing import Any

import pytest

from app.application.auth.messages import AUTH_MODE_FIRST, LOGIN_FAILED, SETUP_CLOSED
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.local_account_http import (
    CONFIG,
    LOGIN,
    ME,
    PASSWORD,
    SETUP,
    SETUP_MODE,
    SETUP_STORAGE,
    anonymous,
    error_locations,
    local_system,
    problem,
)

FLAGS = {
    "dev_login",
    "directory_login",
    "needs_directory_setup",
    "needs_storage_setup",
    "needs_admin_setup",
    "auth_mode",
}


def _setup_body(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    return {"login_id": "kim", "password": PASSWORD, "display_name": "김관리", **overrides}


# ---- GET /auth/config ----


async def test_config_of_a_fresh_system_has_six_flags_and_no_mode() -> None:
    async with anonymous(FakeUseCases()) as http:
        body = (await http.get(CONFIG)).json()

    assert set(body) == FLAGS
    assert body["auth_mode"] is None
    assert (body["needs_directory_setup"], body["needs_storage_setup"]) == (True, True)


async def test_config_reports_the_chosen_mode() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    async with anonymous(use_cases) as http:
        body = (await http.get(CONFIG)).json()

    assert body["auth_mode"] == "local"
    assert body["needs_directory_setup"] is False
    assert body["needs_storage_setup"] is True


async def test_config_of_a_legacy_system_with_an_admin_reports_ad() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_user("boss", Role.ADMIN)
    async with anonymous(use_cases) as http:
        body = (await http.get(CONFIG)).json()

    assert body["auth_mode"] == "ad"


# ---- PUT /auth/setup/auth-mode (AC-1·3) ----


@pytest.mark.parametrize("mode", ["local", "ad"])
async def test_choosing_a_mode_is_204_and_shows_in_the_config(mode: str) -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.put(SETUP_MODE, json={"mode": mode})
        config = (await http.get(CONFIG)).json()

    assert response.status_code == 204
    assert response.content == b""
    assert config["auth_mode"] == mode


async def test_choosing_local_makes_the_directory_step_unnecessary() -> None:
    async with anonymous(FakeUseCases()) as http:
        await http.put(SETUP_MODE, json={"mode": "local"})
        config = (await http.get(CONFIG)).json()

    assert (config["needs_directory_setup"], config["needs_storage_setup"]) == (False, True)
    assert config["needs_admin_setup"] is False


async def test_the_mode_can_be_changed_before_the_first_admin() -> None:
    async with anonymous(FakeUseCases()) as http:
        await http.put(SETUP_MODE, json={"mode": "local"})
        response = await http.put(SETUP_MODE, json={"mode": "ad"})
        config = (await http.get(CONFIG)).json()

    assert response.status_code == 204
    assert config["auth_mode"] == "ad"


@pytest.mark.parametrize("mode", ["local", "ad"])
async def test_choosing_a_mode_after_the_first_admin_is_409_setup_closed(mode: str) -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_user("boss", Role.ADMIN)
    async with anonymous(use_cases) as http:
        response = await http.put(SETUP_MODE, json={"mode": mode})

    assert problem(response, 409, "invalid-state")["detail"] == SETUP_CLOSED


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"mode": None},
        {"mode": ""},
        {"mode": "oidc"},
        {"mode": "LOCAL"},
        {"mode": 1},
        {"mode": "local", "extra": 1},
    ],
)
async def test_choosing_a_mode_with_an_invalid_body_is_422(body: dict[str, Any]) -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.put(SETUP_MODE, json=body)
        config = (await http.get(CONFIG)).json()

    problem(response, 422, "request-validation")
    assert config["auth_mode"] is None


async def test_choosing_a_mode_needs_the_csrf_header() -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.request(
            "PUT", SETUP_MODE, json={"mode": "local"}, headers={"X-Requested-With": ""}
        )

    problem(response, 403, "csrf")


# ---- PUT /auth/setup/storage 선행 조건 (AC-2) ----


async def test_storage_step_before_choosing_a_mode_is_409_auth_mode_first() -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.put(SETUP_STORAGE, json={"path": "/data/neoine/files"})

    assert problem(response, 409, "invalid-state")["detail"] == AUTH_MODE_FIRST


async def test_storage_step_in_local_mode_needs_no_directory() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    async with anonymous(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": "/data/neoine/files"})
        config = (await http.get(CONFIG)).json()

    assert response.status_code == 200, response.text
    assert (config["needs_storage_setup"], config["needs_admin_setup"]) == (False, True)


# ---- POST /auth/setup (AC-4) ----


async def test_local_setup_creates_the_admin_and_signs_in() -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(
            SETUP, json=_setup_body(email="Kim@Corp.test", phone="010-1234-5678")
        )
        me = await http.get(ME)
        config = (await http.get(CONFIG)).json()

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["subject"], body["role"], body["name"], body["email"]) == (
        "kim",
        "admin",
        "김관리",
        "kim@corp.test",
    )
    assert "password" not in response.text
    assert "neoine_session" in response.headers["set-cookie"]
    assert me.status_code == 200
    assert (config["needs_admin_setup"], config["needs_storage_setup"]) == (False, False)
    assert use_cases.directory.authenticate_calls == []


@pytest.mark.parametrize("password", ["short7!", "1234567", "kim"])
async def test_local_setup_weak_password_is_422_and_the_setup_stays_open(password: str) -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json=_setup_body(password=password))
        config = (await http.get(CONFIG)).json()

    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["password"]]
    assert config["needs_admin_setup"] is True


@pytest.mark.parametrize("name", [None, "", "   "])
async def test_local_setup_without_a_display_name_is_422(name: str | None) -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    body = _setup_body()
    body["display_name"] = name
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json=body)
        omitted = await http.post(SETUP, json={"login_id": "kim", "password": PASSWORD})
        config = (await http.get(CONFIG)).json()

    problem(response, 422, "invalid-value")
    problem(omitted, 422, "invalid-value")
    assert config["needs_admin_setup"] is True


@pytest.mark.parametrize("profile", [{"email": "abc"}, {"phone": "12"}])
async def test_local_setup_invalid_email_or_phone_is_422_invalid_value(
    profile: dict[str, str],
) -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json=_setup_body(**profile))

    problem(response, 422, "invalid-value")


@pytest.mark.parametrize("login_id", ["dev-admin", "dev-sales", "dev-user", "Kim)(uid=*"])
async def test_local_setup_reserved_or_malformed_login_id_is_422(login_id: str) -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json=_setup_body(login_id=login_id))

    problem(response, 422, "invalid-value")


async def test_local_setup_after_the_first_admin_is_409_setup_closed() -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    await use_cases.seed_user("boss", Role.ADMIN)
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json=_setup_body())

    assert problem(response, 409, "invalid-state")["detail"] == SETUP_CLOSED
    assert "neoine_session" not in response.headers.get("set-cookie", "")


async def test_ad_setup_with_profile_fields_is_422() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_directory()
    await use_cases.seed_storage()
    use_cases.directory.add_account("kim", PASSWORD)
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json=_setup_body())

    problem(response, 422, "invalid-value")
    assert use_cases.directory.authenticate_calls == []


async def test_ad_setup_without_profile_fields_still_works_as_before() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    await use_cases.seed_storage()
    use_cases.directory.add_account("kim", "pw-kim", display_name="김영업")
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json={"login_id": "kim", "password": "pw-kim"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "김영업"


async def test_setup_password_is_a_required_field() -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json={"login_id": "kim", "display_name": "김관리"})

    problem(response, 422, "request-validation")


# ---- POST /auth/login (AC-5) ----


async def _local_login_system(use_cases: FakeUseCases) -> None:
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    await use_cases.seed_local_user("kim", PASSWORD, Role.SALES, display_name="김영업")


async def test_local_login_with_the_right_password_is_200_without_a_warning() -> None:
    use_cases = FakeUseCases()
    await _local_login_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})
        me = await http.get(ME)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["subject"], body["role"], body["directory_warning"]) == ("kim", "sales", None)
    assert "neoine_session" in response.headers["set-cookie"]
    assert me.status_code == 200
    assert use_cases.directory.authenticate_calls == []


@pytest.mark.parametrize("login_id", ["kim", "ghost"])
async def test_local_login_wrong_password_and_unknown_id_get_the_same_401(login_id: str) -> None:
    use_cases = FakeUseCases()
    await _local_login_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(LOGIN, json={"login_id": login_id, "password": "wrong-pass-1"})

    body = problem(response, 401, "unauthenticated")
    assert body["detail"] == LOGIN_FAILED
    assert "neoine_session" not in response.headers.get("set-cookie", "")


async def test_local_login_of_a_resigned_user_is_the_same_401() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    gone = await use_cases.seed_local_user("gone", PASSWORD)
    await use_cases.resign_user(gone.id)
    async with anonymous(use_cases) as http:
        response = await http.post(LOGIN, json={"login_id": "gone", "password": PASSWORD})

    assert problem(response, 401, "unauthenticated")["detail"] == LOGIN_FAILED


async def test_local_login_failures_lock_the_account_with_429() -> None:
    use_cases = FakeUseCases()
    await _local_login_system(use_cases)
    async with anonymous(use_cases) as http:
        for _ in range(MAX_PER_ACCOUNT):
            await http.post(LOGIN, json={"login_id": "kim", "password": "wrong-pass-1"})
        locked = await http.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})

    problem(locked, 429, "too-many-attempts")


@pytest.mark.parametrize("password", ["", "   "])
async def test_local_setup_blank_password_is_422_on_the_password_field(password: str) -> None:
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json=_setup_body(password=password))
        config = (await http.get(CONFIG)).json()

    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["password"]]
    assert config["needs_admin_setup"] is True


@pytest.mark.parametrize("password", ["", "   "])
async def test_ad_setup_blank_password_stays_the_login_failure_401(password: str) -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_directory()
    await use_cases.seed_storage()
    async with anonymous(use_cases) as http:
        response = await http.post(SETUP, json={"login_id": "kim", "password": password})

    assert problem(response, 401, "unauthenticated")["detail"] == LOGIN_FAILED
    assert use_cases.directory.authenticate_calls == []
