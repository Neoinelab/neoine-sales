"""AD(디렉터리) 설정 관리 step: 설정 조회·저장·연결 테스트와 관련 상태 준비·확인.

회사 AD는 `api.directory`(Port 대역)로 대체된다(사유는 `tests/functional/conftest.py`).
AD가 받은 호출 기록(`authenticate_calls`, `probe_calls`)은 "AD를 호출하지 않았다/이 설정으로
호출했다"를 확인하는 Then에만 쓴다.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.functional.conftest import make_settings
from tests.functional.steps.auth import (
    ADMIN_LOGIN,
    CONFIG,
    LOGIN,
    ME,
    directory_payload,
    given_directory_configured,
    password_of,
)
from tests.support.functional_clock import active_clock

if TYPE_CHECKING:
    from httpx import Response

    from app.application.ports.directory import DirectoryError
    from tests.functional.conftest import Api

SETTINGS = "/api/v1/settings/directory"
SETTINGS_TEST = "/api/v1/settings/directory/test"
DEV_LOGIN = "/api/v1/auth/dev-login"
SESSION_COOKIE = "neoine_session"
CSRF_HEADER_NAME = "X-Requested-With"
NEW_DN = "dc=new,dc=test"
STORED_DN = "dc=corp,dc=test"
ADMIN_PASSWORD = password_of(ADMIN_LOGIN)
WRONG_PASSWORD = "wrong-password"  # noqa: S105 - 가짜 값
SETTINGS_FIELDS = {
    "server_urls",
    "use_starttls",
    "ca_cert_pem",
    "bind_template",
    "base_dn",
    "user_filter",
    "display_name_attribute",
    "email_attribute",
    "connect_timeout_seconds",
    "receive_timeout_seconds",
    "revision",
    "updated_at",
    "updated_by",
}
USER_REF_FIELDS = {"id", "name", "resigned", "label", "role"}
MAX_FAILURES_PER_ACCOUNT = make_settings(
    "postgresql+asyncpg://u:p@h/d"
).login_max_failures_per_account


def update_payload(
    expected_revision: int = 1, password: str | None = ADMIN_PASSWORD, **overrides: object
) -> dict[str, Any]:
    """PUT /settings/directory 본문: 설정 필드 + expected_revision + 현재 admin의 password."""
    return {
        **directory_payload(**overrides),
        "expected_revision": expected_revision,
        "password": password,
    }


def probe_payload(password: str | None = ADMIN_PASSWORD, **overrides: object) -> dict[str, Any]:
    """POST /settings/directory/test 본문: 설정 필드 + 현재 admin의 password."""
    return {**directory_payload(**overrides), "password": password}


# ---------------------------------------------------------------- Given


def given_no_directory_calls_yet(api: Api) -> None:
    """AD가 받은 호출 기록을 비운다(앞선 로그인·설정 호출과 구분하려는 것)."""
    api.directory.authenticate_calls.clear()
    api.directory.probe_calls.clear()


def given_directory_fails_with(api: Api, error: DirectoryError) -> None:
    """AD 인증 호출이 해당 오류로 실패한다."""
    api.directory.fail_with = error


def given_directory_probe_fails_with(api: Api, error: DirectoryError) -> None:
    api.directory.probe_fails_with = error


def given_admin_directory_password(api: Api, password: str) -> None:
    """AD에서 admin(`root`)의 비밀번호가 주어진 값이다(이미 열린 세션은 그대로)."""
    api.directory.add_account(ADMIN_LOGIN, password)


async def given_settings_saved(
    api: Api, *, expected_revision: int = 1, base_dn: str = NEW_DN
) -> None:
    """admin이 Base DN을 바꿔 설정을 한 번 저장해 두었다."""
    response = await api.put(SETTINGS, json=update_payload(expected_revision, base_dn=base_dn))
    assert response.status_code == 200, response.text


async def given_wrong_password_attempts(api: Api, *, endpoint: str) -> None:
    """같은 admin 계정이 틀린 비밀번호로 시도 제한 횟수만큼 실패했다."""
    for _ in range(MAX_FAILURES_PER_ACCOUNT):
        if endpoint == SETTINGS:
            await api.put(SETTINGS, json=update_payload(password=WRONG_PASSWORD))
        else:
            await api.post(SETTINGS_TEST, json=probe_payload(password=WRONG_PASSWORD))


async def given_settings_row_removed(api: Api) -> None:
    """저장된 AD 설정 행이 없다(공개 API로는 만들 수 없는 상태라 DB에서 직접 지운다)."""
    await _execute(api, "delete from directory_settings")


async def given_dev_login_admin(api: Api) -> None:
    """AD 설정 1단계만 끝난 상태에서 개발용 로그인(admin)으로 들어와 있다."""
    await given_directory_configured(api)
    response = await api.post(DEV_LOGIN, json={"role": "admin"})
    assert response.status_code == 200, response.text


async def given_session_token(api: Api, *, login_id: str) -> str:
    """사용자로 로그인해 세션 토큰을 받아 둔다(이후 요청에서 그 세션을 따로 쓰려는 것).

    부수 효과: 클라이언트 쿠키가 그 사용자의 세션으로 바뀐다.
    """
    credentials = {"login_id": login_id, "password": password_of(login_id)}
    response = await api.post(LOGIN, json=credentials)
    assert response.status_code == 200, response.text
    token = response.cookies.get(SESSION_COOKIE)
    assert token, "로그인 응답에 세션 쿠키가 없다"
    return token


# ---------------------------------------------------------------- When


async def when_read_settings(api: Api) -> Response:
    return await api.get(SETTINGS)


async def when_update_settings(api: Api, payload: dict[str, Any]) -> Response:
    return await api.put(SETTINGS, json=payload)


async def when_test_connection(api: Api, payload: dict[str, Any]) -> Response:
    return await api.post(SETTINGS_TEST, json=payload)


async def when_update_settings_without_csrf_header(api: Api) -> Response:
    # 값이 빈 헤더는 서버가 "없음"으로 취급한다(클라이언트 기본 헤더를 덮어쓰는 방법)
    return await api.request("PUT", SETTINGS, json=update_payload(), headers={CSRF_HEADER_NAME: ""})


async def when_test_connection_without_csrf_header(api: Api) -> Response:
    return await api.request(
        "POST", SETTINGS_TEST, json=probe_payload(), headers={CSRF_HEADER_NAME: ""}
    )


async def when_log_in(api: Api, login_id: str) -> Response:
    return await api.post(LOGIN, json={"login_id": login_id, "password": password_of(login_id)})


# ---------------------------------------------------------------- Then


async def then_stored_settings_are(api: Api, *, revision: int, base_dn: str) -> None:
    stored = (await api.get(SETTINGS)).json()
    assert (stored["revision"], stored["base_dn"]) == (revision, base_dn)


async def then_stored_revision_is(api: Api, revision: int) -> None:
    assert (await api.get(SETTINGS)).json()["revision"] == revision


def then_directory_not_called(api: Api) -> None:
    assert api.directory.authenticate_calls == []
    assert api.directory.probe_calls == []


def then_directory_authenticated_once(
    api: Api, *, login_id: str, password: str, base_dn: str
) -> None:
    (call,) = api.directory.authenticate_calls
    assert (call.login_id.value, call.password, call.settings.base_dn) == (
        login_id,
        password,
        base_dn,
    )


def then_updated_by_is_user_ref(body: dict[str, Any], *, user_id: int, name: str) -> None:
    updated_by = body["updated_by"]
    assert updated_by["id"] == user_id
    assert updated_by["name"] == name
    assert set(updated_by) == USER_REF_FIELDS
    assert updated_by["resigned"] is False


def then_updated_at_is_just_now(body: dict[str, Any]) -> None:
    """저장 시각이 시나리오 시계의 현재 값과 정확히 같다(설정은 Given에서 이 시각에 저장됐다)."""
    updated_at = datetime.fromisoformat(body["updated_at"])
    assert updated_at.tzinfo is not None
    assert updated_at == active_clock().now(), (body["updated_at"], active_clock().now())


async def current_user_id(api: Api) -> int:
    return int((await api.get(ME)).json()["user_id"])


async def then_config_offers_directory_login(api: Api) -> None:
    assert (await api.get(CONFIG)).json()["directory_login"] is True


async def _execute(api: Api, statement: str) -> None:
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def dump_tables(api: Api, tables: tuple[str, ...]) -> dict[str, str]:
    """테이블마다 모든 행을 문자열로 펼친다(저장된 내용에 특정 값이 없는지 보려는 것)."""
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    dumped: dict[str, str] = {}
    try:
        async with engine.connect() as connection:
            for table in tables:
                rows = await connection.execute(text(f"select t::text from {table} t"))  # noqa: S608
                dumped[table] = "\n".join(row[0] for row in rows)
    finally:
        await engine.dispose()
    return dumped
