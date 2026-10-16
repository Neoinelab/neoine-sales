"""사용자 관리 영역(등록·목록·삭제/퇴사·선택 목록·역할 반영) step.

Given은 공개 API(최초 설정·사용자 등록·로그인·삭제)로 상태를 만든다. 공개 API가 없는 상태(연결 행,
역할 변경)는 `steps/users_db.py`가 DB에 직접 둔다. 여러 사용자가 동시에 요청하는 시나리오를 위해
로그인한 세션 쿠키를 `Session`으로 따로 들고 다닌다.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Final

from tests.functional.steps.auth import (
    ADMIN_LOGIN,
    LOGIN,
    USERS,
    RoleName,
    given_ad_account,
    given_user_registered,
    password_of,
)
from tests.functional.steps.common import then_status_is
from tests.support.functional_clock import active_clock

if TYPE_CHECKING:
    from collections.abc import Sequence

    from httpx import Response

    from tests.functional.conftest import Api

OPTIONS: Final = "/api/v1/user-options"
CONFIG: Final = "/api/v1/auth/config"
DEV_LOGIN: Final = "/api/v1/auth/dev-login"
SESSION_COOKIE: Final = "neoine_session"
CSRF_HEADER: Final = "X-Requested-With"
# 업무 API 접근 여부를 보는 경로(고객 API는 P0에서 바뀐다: 여기만 고치면 된다)
BUSINESS_READ: Final = "/api/v1/deals"  # 로그인한 모든 역할이 읽는다
BUSINESS_WRITE: Final = "/api/v1/bant-labels"  # sales·admin이 쓰고 user는 403이다
BUSINESS_PAYLOAD: Final = {"category": "budget", "name": "역할 변경 확인용 Label"}
USER_KEYS: Final = {
    "id",
    "login_id",
    "role",
    "display_name",
    "email",
    "created_at",
    "created_by",
    "last_login_at",
    "status",
    "deleted_at",
    "delete_reason",
}
USER_REF_KEYS: Final = {"id", "name", "resigned", "label", "role"}  # 참조에는 AD 계정 아이디가 없다
ACTION_GAP_SECONDS: Final = (
    60  # 동작(등록·로그인·삭제) 사이에 시계를 이만큼 전진시켜 시각을 구분한다
)


@dataclass(frozen=True, slots=True)
class Session:
    """로그인한 사용자의 세션 쿠키. 쿠키 저장소와 별개로 요청마다 실어 보낸다."""

    login_id: str
    headers: dict[str, str]


# --------------------------------------------------------------------------- Given


async def log_in(api: Api, login_id: str) -> Response:
    """주어진 아이디로 로그인한다(쿠키 저장소에 세션이 담긴다). 시계는 움직이지 않는다."""
    response = await _post_login(api, login_id)
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"
    return response


async def capture_session(api: Api, login_id: str) -> Session:
    """로그인해 세션 쿠키를 `Session`으로 받아 둔다(쿠키 저장소에도 그 세션이 남는다)."""
    token = (await log_in(api, login_id)).cookies.get(SESSION_COOKIE)
    assert token, "로그인 응답에 세션 쿠키가 없다"
    return Session(login_id, {"Cookie": f"{SESSION_COOKIE}={token}"})


async def given_signed_in_session(api: Api, *, login_id: str, role: RoleName) -> Session:
    """사용자를 등록하고 그 사용자의 세션을 받아 둔다. 끝나면 admin(root)이 로그인 상태다."""
    await given_user_registered(api, login_id=login_id, role=role)
    session = await capture_session(api, login_id)
    await log_in(api, ADMIN_LOGIN)
    return session


async def given_user_signed_in_once(
    api: Api,
    *,
    login_id: str,
    role: RoleName,
    display_name: str | None = None,
    email: str | None = None,
) -> str:
    """AD 프로필(표시 이름·이메일)이 있는 사용자를 등록하고 한 번 로그인시킨다(프로필이 저장된다).

    끝나면 admin(root)이 로그인 상태다. 사용자 id를 돌려준다.
    """
    user_id = await given_user_registered(api, login_id=login_id, role=role)
    given_ad_account(api, login_id=login_id, display_name=display_name, email=email)
    await log_in(api, login_id)
    await log_in(api, ADMIN_LOGIN)
    return user_id


async def given_user_deleted(api: Api, user_id: str) -> None:
    """admin이 사용자를 삭제했다(200)."""
    response = await api.delete(f"{USERS}/{user_id}")
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"


async def given_dev_login(api: Api, role: RoleName) -> None:
    """개발용 로그인(dev-login)으로 해당 역할의 개발 사용자로 로그인했다."""
    response = await api.post(DEV_LOGIN, json={"role": role})
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"


async def id_of(api: Api, login_id: str, *, status: str = "active") -> str:
    """admin 세션으로 목록을 조회해 로그인 아이디의 사용자 id를 찾는다."""
    response = await api.get(USERS, params={"status": status})
    return str(next(i["id"] for i in response.json()["items"] if i["login_id"] == login_id))


def directory_calls(api: Api) -> int:
    """지금까지 AD(Fake)에 들어간 인증·연결 시험 호출 수. 이후 증가 여부를 보려는 기준값."""
    return len(api.directory.authenticate_calls) + len(api.directory.probe_calls)


# --------------------------------------------------------------------------- When


async def _post_login(api: Api, login_id: str) -> Response:
    return await api.post(LOGIN, json={"login_id": login_id, "password": password_of(login_id)})


async def when_login(api: Api, login_id: str) -> Response:
    """로그인한다. 직전 동작과 시각이 구분되도록 시계를 전진시킨 뒤 요청한다."""
    api.clock.advance(ACTION_GAP_SECONDS)
    return await _post_login(api, login_id)


async def when_list_users(api: Api, **params: str | int | list[str]) -> Response:
    return await api.get(USERS, params=params)


async def when_register_user(
    api: Api, *, login_id: str, role: str, display_name: str | None = None
) -> Response:
    """사용자를 등록한다(display_name은 주었을 때만 본문에 싣는다).

    등록자의 로그인 시각과 구분되도록 시계를 전진시킨 뒤 요청한다.
    """
    api.clock.advance(ACTION_GAP_SECONDS)
    body: dict[str, object] = {"login_id": login_id, "role": role}
    if display_name is not None:
        body["display_name"] = display_name
    return await api.post(USERS, json=body)


async def when_register_with_body(api: Api, body: dict[str, object]) -> Response:
    return await api.post(USERS, json=body)


async def when_delete_user(api: Api, user_id: str, **params: str | int | list[str]) -> Response:
    """사용자를 삭제(퇴사)한다. 이전 동작과 구분되도록 시계를 전진시킨 뒤 요청한다."""
    api.clock.advance(ACTION_GAP_SECONDS)
    return await api.request("DELETE", f"{USERS}/{user_id}", params=params)


async def when_request_as(
    api: Api, session: Session, method: str, url: str, *, json: object = None
) -> Response:
    return await api.request(method, url, json=json, headers=session.headers)


async def when_list_options(api: Api, **params: str | int | list[str]) -> Response:
    return await api.get(OPTIONS, params=params)


# --------------------------------------------------------------------------- Then


def then_logins_are(response: Response, expected: Sequence[str]) -> None:
    """목록 응답의 login_id가 순서까지 같다."""
    then_status_is(response, 200)
    assert [item["login_id"] for item in response.json()["items"]] == list(expected)


def then_names_are(response: Response, expected: Sequence[str]) -> None:
    """선택 목록 응답의 표시 이름이 순서까지 같다."""
    then_status_is(response, 200)
    assert [item["name"] for item in response.json()["items"]] == list(expected)


def then_problem_type_is_one_of(response: Response, *, status: int, suffixes: set[str]) -> None:
    then_status_is(response, status)
    assert any(str(response.json()["type"]).endswith(s) for s in suffixes), response.json()


def then_is_scenario_now(timestamp: object) -> None:
    """시각이 시나리오 시계의 현재 값과 정확히 같다(그 동작이 일어난 순간).

    등록·로그인·삭제 When은 요청 전에 시계를 전진시키므로, 이 값은 직전 동작의 시각이다.
    다른 필드의 시각(예: 등록 시각 대신 last_login_at)이나 실제 시각이 나가면 실패한다.
    """
    parsed = datetime.fromisoformat(str(timestamp))
    assert parsed == active_clock().now(), (timestamp, active_clock().now())


async def then_logins_listed(api: Api, expected: Sequence[str], *, status: str = "active") -> None:
    """admin 세션으로 상태 필터에 맞는 목록을 다시 조회하면 login_id가 순서까지 같다."""
    then_logins_are(await api.get(USERS, params={"status": status}), expected)


def then_first_setup_stays_closed(response: Response) -> None:
    """인증 설정 응답이 최초 설정(AD 설정·admin 생성)이 끝났음을 알린다."""
    then_status_is(response, 200)
    config = response.json()
    assert (
        config["needs_directory_setup"],
        config["needs_storage_setup"],
        config["needs_admin_setup"],
    ) == (False, False, False)


def then_directory_untouched_since(api: Api, baseline: int) -> None:
    """AD(Fake)에 새 인증·연결 시험 호출이 없었다."""
    assert directory_calls(api) == baseline
