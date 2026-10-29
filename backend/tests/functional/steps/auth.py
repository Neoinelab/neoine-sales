"""모든 영역이 쓰는 인증 Given step: AD 계정, 최초 설정, 사용자 등록, 역할별 로그인·로그아웃.

사전 상태는 공개 API(최초 설정·사용자 등록·로그인)로 만든다. AD 계정만 Port 대역
(`api.directory`)에 직접 둔다(외부 대체 사유는 `tests/functional/conftest.py`).
로그인·최초 설정 자체를 검증하는 When/Then step은 이 모듈이 아니라 auth 영역 모듈에 둔다.
"""

from typing import TYPE_CHECKING, Literal

from tests.factories_auth import BIND_ACCOUNT, BIND_PASSWORD, USER_FILTER

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

RoleName = Literal["admin", "sales", "user"]

LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
SETUP = "/api/v1/auth/setup"
SETUP_DIRECTORY = "/api/v1/auth/setup/directory"
SETUP_STORAGE = "/api/v1/auth/setup/storage"
SETUP_STORAGE_TEST = "/api/v1/auth/setup/storage/test"
CONFIG = "/api/v1/auth/config"
ME = "/api/v1/auth/me"
USERS = "/api/v1/users"

ADMIN_LOGIN = "root"
ADMIN_NAME = "관리자"


def password_of(login_id: str) -> str:
    """테스트 AD 계정의 더미 비밀번호 규칙."""
    return f"pw-{login_id}"


def directory_payload(**overrides: object) -> dict[str, object]:
    """AD 연결 설정 본문(최초 설정 1단계의 요청 본문). 유효한 더미 값 7개: 호스트·포트·보안 연결·
    바인드 계정·바인드 비밀번호·사용자 필터·연결 제한 시간. Base DN은 서버가 AD에서 찾는다."""
    values: dict[str, object] = {
        "host": "dc1.corp.test",
        "port": 636,
        "security": "ssl",
        "bind_account": BIND_ACCOUNT,
        "bind_password": BIND_PASSWORD,
        "user_filter": USER_FILTER,
        "connect_timeout_seconds": 5,
    }
    return {**values, **overrides}


def _expect(response: Response, *statuses: int) -> Response:
    assert response.status_code in statuses, f"Given 실패 {response.status_code}: {response.text}"
    return response


def given_ad_account(
    api: Api, *, login_id: str, display_name: str | None = None, email: str | None = None
) -> None:
    """회사 AD에 계정이 있다(비밀번호는 `password_of(login_id)`)."""
    api.directory.add_account(
        login_id, password_of(login_id), display_name=display_name, email=email
    )


async def given_directory_configured(api: Api) -> None:
    """최초 설정 1단계(AD 연결 설정 저장)가 끝나 있다. 이미 끝났으면 아무것도 하지 않는다."""
    if (await api.get(CONFIG)).json()["needs_directory_setup"]:
        _expect(await api.put(SETUP_DIRECTORY, json=directory_payload()), 200)


def storage_path_of(api: Api) -> str:
    """이 시나리오의 파일 저장 위치(tmp_path 아래 실제 디렉터리)."""
    assert api.storage_root is not None, "이 Api에는 저장 위치 디렉터리가 없다"
    return str(api.storage_root)


async def given_storage_configured(api: Api) -> None:
    """최초 설정 2단계(파일 저장 위치 저장)가 끝나 있다. AD 설정(1단계)이 먼저 끝나 있어야 한다.

    이미 끝났거나 최초 admin이 있어 설정이 닫혔으면 아무것도 하지 않는다.
    """
    if (await api.get(CONFIG)).json()["needs_storage_setup"]:
        _expect(await api.put(SETUP_STORAGE, json={"path": storage_path_of(api)}), 200)


async def given_setup_prerequisites_configured(api: Api) -> None:
    """최초 admin 지정 전 단계(1단계 AD 연결, 2단계 파일 저장 위치)가 모두 끝나 있다."""
    await given_directory_configured(api)
    await given_storage_configured(api)


async def given_admin_exists(api: Api) -> None:
    """최초 설정(1~3단계)이 끝나 최초 admin(`root`)이 있다. 3단계를 거치면 root로 로그인된다."""
    await given_setup_prerequisites_configured(api)
    if (await api.get(CONFIG)).json()["needs_admin_setup"]:
        given_ad_account(api, login_id=ADMIN_LOGIN, display_name=ADMIN_NAME)
        credentials = {"login_id": ADMIN_LOGIN, "password": password_of(ADMIN_LOGIN)}
        _expect(await api.post(SETUP, json=credentials), 200)


async def given_logged_out(api: Api) -> None:
    """로그아웃해 익명 사용자다(서버 세션도 끝낸다)."""
    _expect(await api.post(LOGOUT), 204)
    api.forget_session()


async def _log_in(api: Api, login_id: str) -> None:
    credentials = {"login_id": login_id, "password": password_of(login_id)}
    _expect(await api.post(LOGIN, json=credentials), 200)


async def given_user_registered(api: Api, *, login_id: str, role: RoleName) -> int:
    """admin이 AD 계정이 있는 사용자를 역할과 함께 등록해 두었다. 사용자 id를 돌려준다.

    부수 효과: 등록하려고 admin(`root`)으로 로그인한 상태가 된다.
    """
    await given_admin_exists(api)
    # 등록 순서가 시각으로 드러나도록(목록은 created_at 순) 사용자마다 시계를 전진시킨다
    api.clock.advance(60)
    await _log_in(api, ADMIN_LOGIN)
    given_ad_account(api, login_id=login_id, display_name=f"사용자 {login_id}")
    created = _expect(await api.post(USERS, json={"login_id": login_id, "role": role}), 201)
    return int(created.json()["id"])


async def given_logged_in_as(
    api: Api, *, role: RoleName = "admin", login_id: str | None = None
) -> str:
    """주어진 역할의 재직 사용자로 로그인해 있다. 로그인 아이디를 돌려준다.

    admin이고 login_id가 없으면 최초 admin(`root`), 그 밖에는 `<role>-user`(또는 login_id)를
    admin이 등록한 뒤 그 사용자로 로그인한다.
    """
    await given_admin_exists(api)
    if role == "admin" and login_id in (None, ADMIN_LOGIN):
        await _log_in(api, ADMIN_LOGIN)
        return ADMIN_LOGIN
    target = login_id or f"{role}-user"
    await given_user_registered(api, login_id=target, role=role)
    await _log_in(api, target)
    return target
