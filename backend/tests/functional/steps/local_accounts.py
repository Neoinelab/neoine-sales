"""앱 자체 계정 관리(local 모드) feature의 step: 최초 설정, 로그인, 사용자 등록·수정, 내 정보.

사전 상태는 공개 API(인증 방식 -> 저장 위치 -> 첫 admin 등록 -> 사용자 등록 -> 로그인)로 만든다.
local 모드에는 AD가 없으므로 `api.directory`는 쓰지 않는다. 회사 AD(Port 대역)를 쓰는 시나리오는
기존 step(`steps/auth.py`)을 쓴다.
"""

from typing import TYPE_CHECKING, Any, Literal

from tests.functional.steps.auth import (
    CONFIG,
    LOGIN,
    ME,
    SETUP,
    SETUP_STORAGE,
    USERS,
    RoleName,
    given_ad_account,
    given_directory_configured,
    password_of,
    storage_path_of,
)
from tests.functional.steps.login_db import sql_rows
from tests.functional.steps.session import SESSION_COOKIE, session_header
from tests.functional.steps.users import Session

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

SETUP_AUTH_MODE = "/api/v1/auth/setup/auth-mode"
MY_PROFILE = "/api/v1/me/profile"
MY_PASSWORD = "/api/v1/me/password"  # noqa: S105 - 경로다
ADMIN_LOGIN = "root"
ADMIN_NAME = "관리자"
Mode = Literal["ad", "local"]


def local_password_of(login_id: str) -> str:
    """local 모드 테스트 계정의 더미 비밀번호 규칙(8자 이상이고 아이디와 같지 않다)."""
    return f"pw-{login_id}-1234"


def _expect(response: Response, *statuses: int) -> Response:
    assert response.status_code in statuses, f"Given 실패 {response.status_code}: {response.text}"
    return response


def setup_body(**overrides: object) -> dict[str, object]:
    """local 최초 admin 등록 본문(유효한 더미 값). 아이디를 바꾸면 비밀번호도 따라 바뀐다."""
    login_id = str(overrides.get("login_id", ADMIN_LOGIN))
    values: dict[str, object] = {
        "login_id": login_id,
        "password": local_password_of(login_id),
        "display_name": ADMIN_NAME,
    }
    return {**values, **overrides}


def user_body(login_id: str, role: str = "sales", **overrides: object) -> dict[str, object]:
    """local 사용자 등록 본문(유효한 더미 값)."""
    values: dict[str, object] = {
        "login_id": login_id,
        "role": role,
        "password": local_password_of(login_id),
        "display_name": f"사용자 {login_id}",
    }
    return {**values, **overrides}


# ---------------------------------------------------------------------------- Given


async def given_auth_mode_chosen(api: Api, mode: Mode = "local") -> None:
    """최초 설정 1단계에서 인증 방식을 골랐다."""
    _expect(await api.put(SETUP_AUTH_MODE, json={"mode": mode}), 204)


async def given_local_storage_step_done(api: Api) -> None:
    """local 모드로 1단계(인증 방식)와 2단계(저장 위치)를 마쳤다. 첫 admin 등록만 남는다."""
    await given_auth_mode_chosen(api, "local")
    _expect(await api.put(SETUP_STORAGE, json={"path": storage_path_of(api)}), 200)


async def given_local_system_ready(api: Api, **profile: object) -> None:
    """local 모드로 최초 설정 3단계를 마쳤다. 첫 admin(`root`)이 로그인된 상태다."""
    await given_local_storage_step_done(api)
    _expect(await api.post(SETUP, json=setup_body(**profile)), 200)


async def given_local_admin_logged_in(api: Api) -> None:
    """local 시스템이 준비돼 있고 admin(`root`)으로 로그인해 있다."""
    config = (await api.get(CONFIG)).json()
    if config["needs_admin_setup"] or config["needs_storage_setup"] or config["auth_mode"] is None:
        await given_local_system_ready(api)
        return
    await log_in_local(api, ADMIN_LOGIN)


async def log_in_local(api: Api, login_id: str, password: str | None = None) -> Response:
    """local 계정으로 로그인한다(쿠키 저장소에 세션이 담긴다). 성공해야 한다."""
    body = {"login_id": login_id, "password": password or local_password_of(login_id)}
    return _expect(await api.post(LOGIN, json=body), 200)


async def given_local_user_registered(
    api: Api, *, login_id: str, role: RoleName = "sales", **profile: object
) -> int:
    """admin이 local 사용자를 등록해 두었다. 사용자 id를 돌려준다.

    부수 효과: 등록하려고 admin(`root`)으로 로그인한 상태가 된다.
    """
    await given_local_admin_logged_in(api)
    api.clock.advance(60)
    created = _expect(await api.post(USERS, json=user_body(login_id, role, **profile)), 201)
    return int(created.json()["id"])


async def given_local_user_signed_in(
    api: Api, *, login_id: str, role: RoleName = "sales", **profile: object
) -> int:
    """local 사용자를 등록하고 그 사용자로 로그인했다. 사용자 id를 돌려준다."""
    user_id = await given_local_user_registered(api, login_id=login_id, role=role, **profile)
    await log_in_local(api, login_id)
    return user_id


async def given_local_session(api: Api, *, login_id: str, password: str | None = None) -> Session:
    """로그인해 세션 쿠키를 `Session`으로 받아 둔다(쿠키 저장소도 그 세션으로 바뀐다)."""
    response = await log_in_local(api, login_id, password)
    token = response.cookies.get(SESSION_COOKIE)
    assert token, "로그인 응답에 세션 쿠키가 없다"
    return Session(login_id, session_header(token))


async def given_local_user_resigned(api: Api, *, user_id: int) -> None:
    """admin이 사용자를 퇴사(삭제) 처리했다. admin 세션이 필요하다."""
    _expect(await api.delete(f"{USERS}/{user_id}"), 200)


async def given_ad_system_with_user(
    api: Api, *, login_id: str, role: RoleName = "sales", display_name: str = "김영업"
) -> None:
    """AD 모드로 최초 설정이 끝났고 AD 계정이 있는 사용자가 로그인해 있다."""
    from tests.functional.steps.auth import given_user_registered  # noqa: PLC0415

    await given_user_registered(api, login_id=login_id, role=role)
    given_ad_account(
        api, login_id=login_id, display_name=display_name, email=f"{login_id}@corp.test"
    )
    _expect(
        await api.post(LOGIN, json={"login_id": login_id, "password": password_of(login_id)}), 200
    )


async def given_directory_saved_in_ad_mode(api: Api) -> None:
    """(AD 모드) 최초 설정 1단계를 AD 연결 저장으로 마쳤다."""
    await given_directory_configured(api)


# ---------------------------------------------------------------------------- When


async def when_choose_auth_mode(api: Api, mode: str) -> Response:
    return await api.put(SETUP_AUTH_MODE, json={"mode": mode})


async def when_set_up_local_admin(api: Api, **overrides: object) -> Response:
    return await api.post(SETUP, json=setup_body(**overrides))


async def when_log_in_local(api: Api, login_id: str, password: str | None = None) -> Response:
    body = {
        "login_id": login_id,
        "password": local_password_of(login_id) if password is None else password,
    }
    return await api.post(LOGIN, json=body)


async def when_register_local_user(api: Api, body: dict[str, object]) -> Response:
    api.clock.advance(60)
    return await api.post(USERS, json=body)


async def when_reset_password(api: Api, user_id: object, password: object) -> Response:
    return await api.put(f"{USERS}/{user_id}/password", json={"password": password})


async def when_patch_user(api: Api, user_id: object, body: dict[str, Any]) -> Response:
    return await api.patch(f"{USERS}/{user_id}", json=body)


async def when_list_users(api: Api) -> Response:
    return await api.get(USERS)


async def when_get_my_profile(api: Api) -> Response:
    return await api.get(MY_PROFILE)


async def when_patch_my_profile(api: Api, body: dict[str, Any]) -> Response:
    return await api.patch(MY_PROFILE, json=body)


async def when_change_my_password(
    api: Api, *, current: str, new: str, headers: dict[str, str] | None = None
) -> Response:
    return await api.request(
        "PUT", MY_PASSWORD, json={"current_password": current, "new_password": new}, headers=headers
    )


async def when_get_me(api: Api) -> Response:
    return await api.get(ME)


# ---------------------------------------------------------------------------- Then


async def then_auth_config_is(api: Api, **expected: object) -> None:
    """GET /auth/config 의 해당 필드가 그 값이다."""
    body = (await api.get(CONFIG)).json()
    assert {key: body.get(key) for key in expected} == expected, body


async def then_session_is_alive(api: Api, session: Session) -> None:
    response = await api.request("GET", ME, headers=session.headers)
    assert response.status_code == 200, response.text


async def then_session_is_ended(api: Api, session: Session) -> None:
    response = await api.request("GET", ME, headers=session.headers)
    assert response.status_code == 401, response.text


async def then_user_exists(api: Api, *, login_id: str, active: bool = True) -> None:
    rows = await sql_rows(
        api,
        "select count(*) from users where login_id = :login_id and (deleted_at is null) = :active",
        login_id=login_id,
        active=active,
    )
    assert rows == [(1,)], rows


async def then_no_user_registered(api: Api, *, login_id: str) -> None:
    rows = await sql_rows(
        api, "select count(*) from users where login_id = :login_id", login_id=login_id
    )
    assert rows == [(0,)], rows


async def then_password_is_stored_only_as_a_hash(api: Api, *, login_id: str, password: str) -> None:
    """해시 행이 있고 평문과 같지 않으며 어느 users 열에도 평문이 없다."""
    rows = await sql_rows(
        api,
        "select h.password_hash from user_password_hashes h join users u on u.id = h.user_id"
        " where u.login_id = :login_id",
        login_id=login_id,
    )
    assert len(rows) == 1, rows
    assert password not in str(rows[0][0])
    leaked = await sql_rows(
        api, "select count(*) from users where users::text like :pattern", pattern=f"%{password}%"
    )
    assert leaked == [(0,)]


def then_body_has_no_password(response: Response, *secrets: str) -> None:
    """응답 본문·헤더에 비밀번호 값이나 password/hash 필드가 없다."""
    exposed = response.text + " ".join(response.headers.values())
    for secret in secrets:
        assert secret not in exposed
    assert '"password' not in response.text
    assert "hash" not in response.text.lower()
