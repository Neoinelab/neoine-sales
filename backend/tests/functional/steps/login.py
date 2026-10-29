"""로그인 feature의 step: 사원 준비, 로그인 요청, 실패·성공 응답 확인.

사전 상태는 공개 API(사용자 등록·로그인)로 만든다. AD는 `api.directory`(Port 대역)다.
세션·쿠키는 `steps/session.py`, DB 조작은 `steps/login_db.py`.
"""

from typing import TYPE_CHECKING

from app.application.auth.messages import LOGIN_FAILED
from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from tests.fakes.auth_stack import MAX_PER_ACCOUNT, MAX_PER_IP
from tests.functional.steps.auth import (
    ADMIN_LOGIN,
    CONFIG,
    LOGIN,
    USERS,
    RoleName,
    given_ad_account,
    given_logged_out,
    given_user_registered,
    password_of,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from httpx import Response

    from app.application.ports.directory import DirectoryError
    from tests.functional.conftest import Api

WITHOUT_CSRF_HEADER = {"X-Requested-With": ""}  # 빈 값은 헤더가 없는 것과 같게 거부된다
LOGIN_FAILED_BODY = {
    "type": "https://neoine-sales.example/problems/unauthenticated",
    "title": "Unauthenticated",
    "status": 401,
    "detail": LOGIN_FAILED,
    "instance": LOGIN,
}
ATTEMPT_LIMIT_PER_ACCOUNT = MAX_PER_ACCOUNT
ATTEMPT_LIMIT_PER_IP = MAX_PER_IP


def credentials(login_id: str = "kim", password: str | None = None) -> dict[str, str]:
    """로그인 본문. 비밀번호를 생략하면 그 AD 계정의 올바른 비밀번호다."""
    return {
        "login_id": login_id,
        "password": password_of(login_id) if password is None else password,
    }


def directory_call_count(api: Api) -> int:
    """지금까지 AD(Port 대역)로 나간 인증 호출 수."""
    return len(api.directory.authenticate_calls)


# ---- Given ----


async def given_employee(
    api: Api,
    *,
    login_id: str = "kim",
    role: RoleName = "sales",
    display_name: str = "김영업",
    email: str = "kim@corp.test",
) -> int:
    """AD 계정이 있고 역할과 함께 등록된 사원이 있다. 로그아웃 상태로 두고 사용자 id를 돌려준다."""
    user_id = await given_user_registered(api, login_id=login_id, role=role)
    given_ad_account(api, login_id=login_id, display_name=display_name, email=email)
    await given_logged_out(api)
    return user_id


async def given_employee_deleted(api: Api, *, user_id: object) -> None:
    """admin이 그 사원을 삭제(퇴사 처리 포함)했다. admin(`root`)으로 로그인한 뒤 로그아웃한다."""
    login = await api.post(LOGIN, json=credentials(ADMIN_LOGIN))
    assert login.status_code == 200, login.text
    deleted = await api.delete(f"{USERS}/{user_id}")
    assert deleted.status_code == 200, deleted.text
    await given_logged_out(api)


async def given_failed_logins(api: Api, *, login_id: str, count: int) -> None:
    """같은 아이디로 틀린 비밀번호 로그인이 count번 실패했다."""
    for _ in range(count):
        response = await api.post(LOGIN, json=credentials(login_id, "wrong-password"))
        assert response.status_code == 401, response.text


async def given_failed_logins_from_many_accounts(api: Api, *, count: int) -> None:
    """같은 IP에서 서로 다른 아이디 count개가 각각 한 번씩 로그인에 실패했다."""
    for number in range(count):
        response = await api.post(LOGIN, json=credentials(f"user{number}", "wrong-password"))
        assert response.status_code == 401, response.text


# ---- When ----


async def when_log_in(api: Api, *, login_id: str = "kim", password: str | None = None) -> Response:
    return await api.post(LOGIN, json=credentials(login_id, password))


async def when_post_login_body(api: Api, body: Mapping[str, object]) -> Response:
    return await api.post(LOGIN, json=body)


async def when_log_in_without_csrf_header(api: Api) -> Response:
    return await api.request("POST", LOGIN, json=credentials(), headers=WITHOUT_CSRF_HEADER)


async def when_log_in_many_times(api: Api, *, login_id: str, times: int) -> list[Response]:
    """올바른 비밀번호로 times번 연달아 로그인한다."""
    return [await when_log_in(api, login_id=login_id) for _ in range(times)]


async def when_log_in_during_each_outage(
    api: Api, errors: Sequence[DirectoryError]
) -> list[Response]:
    """AD 장애 원인을 하나씩 바꿔 가며 같은 로그인 요청을 보낸다."""
    responses: list[Response] = []
    for error in errors:
        api.directory.authenticate_fails_with = error
        responses.append(await when_log_in(api))
    return responses


async def when_submit_password_in_every_outcome(api: Api, password: str) -> list[Response]:
    """같은 비밀번호로 성공·오답(접미사)·너무 긴 값을 낸 뒤, AD 장애 중 해시가 있는 kim(대체 로그인
    성공)과 해시가 없는 lee(503)로 로그인한다."""
    responses = [
        await when_log_in(api, password=password),
        await when_log_in(api, password=password + "x"),
        await when_log_in(api, password=password * 20),
    ]
    api.directory.authenticate_fails_with = DirectoryUnavailableError(
        stage=VerificationStage.CONNECT
    )
    responses.append(await when_log_in(api, password=password))
    responses.append(await when_log_in(api, login_id="lee", password=password))
    return responses


# ---- Then ----


def then_directory_was_not_asked_again(api: Api, *, calls_before: int) -> None:
    assert directory_call_count(api) == calls_before


def then_directory_was_asked_with_base_dn(api: Api, base_dn: str) -> None:
    """가장 최근 AD 인증 호출이 이 base_dn 설정으로 나갔다."""
    assert api.directory.authenticate_calls[-1].base_dn == base_dn


def then_no_cookie_is_set(response: Response) -> None:
    assert response.headers.get_list("set-cookie") == []


def then_login_failed_with_the_common_401(response: Response) -> None:
    """어떤 실패든 같은 401 Problem 본문이고 쿠키가 없다(실패 원인을 구분하지 못한다)."""
    assert response.status_code == 401, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == LOGIN_FAILED_BODY
    then_no_cookie_is_set(response)


def then_signed_in_as(
    response: Response, *, subject: str, email: str | None, name: str, role: str
) -> None:
    """로그인(또는 최초 설정) 응답이 users 행의 id(정수)와 주체 정보를 정확히 담는다.

    로그인 응답의 `directory_warning`은 AD로 정상 로그인했을 때 null이다(최초 설정 응답에는 없다).
    """
    assert response.status_code == 200, response.text
    body = dict(response.json())
    assert body.pop("directory_warning", None) is None
    user_id = body.pop("user_id")
    assert type(user_id) is int
    assert user_id >= 1
    assert body == {"subject": subject, "email": email, "name": name, "role": role}


async def then_last_login_is_recorded(api: Api, *, login_id: str) -> None:
    """admin이 사용자 목록에서 본 그 사원의 최근 로그인 시각이 채워져 있다."""
    await when_log_in(api, login_id=ADMIN_LOGIN)
    items = (await api.get(USERS)).json()["items"]
    recorded = {item["login_id"]: item["last_login_at"] for item in items}
    assert recorded[login_id] is not None


def then_statuses_are_only(responses: list[Response], *allowed: int) -> None:
    assert {response.status_code for response in responses} <= set(allowed)


async def then_auth_flags_are(
    api: Api, *, needs_directory: bool, needs_storage: bool, needs_admin: bool
) -> None:
    """최초 설정 3단계(AD → 저장 위치 → admin)의 진행 플래그가 기대와 같다."""
    body = (await api.get(CONFIG)).json()
    assert (
        body["needs_directory_setup"],
        body["needs_storage_setup"],
        body["needs_admin_setup"],
    ) == (needs_directory, needs_storage, needs_admin)


async def then_password_hash_is_stored_for(api: Api, *, login_id: str, password: str) -> str:
    """그 사용자의 대체 로그인용 해시가 scrypt 형식으로 저장돼 있다. 해시 문자열을 돌려준다.

    평문 비밀번호는 해시 문자열 어디에도 없다.
    """
    from tests.functional.steps.login_db import sql_rows  # noqa: PLC0415

    rows = await sql_rows(
        api,
        "select h.password_hash from user_password_hashes h join users u on u.id = h.user_id"
        " where u.login_id = :login_id",
        login_id=login_id,
    )
    assert len(rows) == 1, rows
    stored = str(rows[0][0])
    assert stored.startswith("scrypt$ln=14,r=8,p=1$"), stored
    assert password not in stored
    return stored


async def then_no_password_hash_is_stored(api: Api, *, login_id: str) -> None:
    from tests.functional.steps.login_db import sql_rows  # noqa: PLC0415

    rows = await sql_rows(
        api,
        "select count(*) from user_password_hashes h join users u on u.id = h.user_id"
        " where u.login_id = :login_id",
        login_id=login_id,
    )
    assert rows == [(0,)]


async def then_failure_count_is(api: Api, expected: int) -> None:
    """kim 계정의 로그인 실패 횟수 카운터 값이다(HMAC 키라 계정별 행 중 가장 큰 값을 본다)."""
    from tests.functional.steps.login_db import sql_rows  # noqa: PLC0415

    rows = await sql_rows(api, "select coalesce(max(failures), 0) from login_failures")
    assert rows == [(expected,)]


async def then_no_password_hash_row_for_user_id(api: Api, user_id: int) -> None:
    """user_password_hashes에 그 사용자 id의 행이 없다(삭제된 사용자의 해시가 남지 않았다)."""
    from tests.functional.steps.login_db import sql_rows  # noqa: PLC0415

    rows = await sql_rows(
        api, "select count(*) from user_password_hashes where user_id = :id", id=user_id
    )
    assert rows == [(0,)]
