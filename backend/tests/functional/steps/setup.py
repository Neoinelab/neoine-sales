"""최초 설정(3단계) feature의 step: 1단계 AD 설정, 2단계 파일 저장 위치, 3단계 최초 admin 지정."""

import json
from typing import TYPE_CHECKING

from app.application.auth.messages import DIRECTORY_FIRST, SETUP_CLOSED
from tests.functional.steps.auth import (
    CONFIG,
    LOGIN,
    SETUP,
    SETUP_DIRECTORY,
    directory_payload,
    given_ad_account,
    given_directory_configured,
    given_setup_prerequisites_configured,
    given_storage_configured,
    password_of,
)
from tests.functional.steps.common import then_response_does_not_mention
from tests.functional.steps.login import WITHOUT_CSRF_HEADER
from tests.functional.steps.login_db import sql_rows
from tests.functional.steps.session import SESSION_COOKIE
from tests.functional.steps.storage import (
    when_save_storage,
    when_save_storage_without_csrf_header,
    when_test_storage_write,
)

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

SETTINGS_KEYS = {
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
SETTINGS = "/api/v1/settings/directory"


def setup_credentials(login_id: str = "kim", password: str | None = None) -> dict[str, str]:
    return {
        "login_id": login_id,
        "password": password_of(login_id) if password is None else password,
    }


def probe_count(api: Api) -> int:
    """지금까지 AD(Port 대역)로 나간 연결 확인(probe) 수."""
    return len(api.directory.probe_calls)


# ---- Given ----


async def given_setup_completed_by(
    api: Api, *, login_id: str = "kim", display_name: str | None = None, email: str | None = None
) -> None:
    """최초 설정이 끝나 있다(그 AD 계정이 최초 admin이고 로그인된 상태)."""
    given_ad_account(api, login_id=login_id, display_name=display_name, email=email)
    await given_setup_prerequisites_configured(api)
    response = await api.post(SETUP, json=setup_credentials(login_id))
    assert response.status_code == 200, response.text


async def given_directory_step_done(api: Api) -> None:
    """최초 설정 1단계(AD 연결 저장)만 끝나 있다."""
    await given_directory_configured(api)


async def given_storage_step_done(api: Api) -> None:
    """최초 설정 1단계(AD 연결)와 2단계(파일 저장 위치)가 끝나 있다. 최초 admin 지정만 남는다."""
    await given_directory_configured(api)
    await given_storage_configured(api)


async def given_reserved_id_was_rejected(api: Api, *, login_id: str) -> None:
    """예약된 아이디로 최초 admin을 지정하려던 시도가 422로 거절됐다."""
    given_ad_account(api, login_id=login_id)
    response = await api.post(SETUP, json=setup_credentials(login_id))
    assert response.status_code == 422, response.text


async def given_failed_setup_attempts(api: Api, *, login_id: str, count: int) -> None:
    """같은 아이디로 틀린 비밀번호 최초 설정 시도가 count번 실패했다."""
    for _ in range(count):
        response = await api.post(SETUP, json=setup_credentials(login_id, "wrong-password"))
        assert response.status_code == 401, response.text


# ---- When ----


async def when_save_directory(api: Api, **overrides: object) -> Response:
    return await api.put(SETUP_DIRECTORY, json=directory_payload(**overrides))


async def when_save_directory_body(api: Api, body: dict[str, object]) -> Response:
    return await api.put(SETUP_DIRECTORY, json=body)


async def when_save_directory_without_csrf_header(api: Api) -> Response:
    return await api.request(
        "PUT", SETUP_DIRECTORY, json=directory_payload(), headers=WITHOUT_CSRF_HEADER
    )


async def when_set_up_admin(
    api: Api, *, login_id: str = "kim", password: str | None = None
) -> Response:
    return await api.post(SETUP, json=setup_credentials(login_id, password))


async def when_set_up_admin_without_csrf_header(api: Api) -> Response:
    return await api.request("POST", SETUP, json=setup_credentials(), headers=WITHOUT_CSRF_HEADER)


async def when_passwords_are_submitted_to_setup_and_login(
    api: Api, *, login_id: str, correct: str, wrong: str
) -> list[Response]:
    """최초 설정과 로그인에 틀린 비밀번호, 올바른 비밀번호를 차례로 낸다."""
    attempts = [
        (SETUP, wrong),
        (SETUP, correct),
        (LOGIN, wrong),
        (LOGIN, correct),
    ]
    return [
        await api.post(url, json={"login_id": login_id, "password": password})
        for url, password in attempts
    ]


async def when_setup_step_is_requested(api: Api, *, step: str, login_id: str = "kim") -> Response:
    """step이 "directory"면 1단계(AD 설정 저장), "storage"면 2단계(파일 저장 위치 저장),
    "storage-test"면 2단계 쓰기 확인, "admin"이면 3단계(최초 admin 지정) 요청이다."""
    if step == "directory":
        return await when_save_directory(api)
    if step == "storage":
        return await when_save_storage(api)
    if step == "storage-test":
        return await when_test_storage_write(api)
    return await when_set_up_admin(api, login_id=login_id)


async def when_setup_step_is_requested_without_csrf_header(api: Api, *, step: str) -> Response:
    if step == "directory":
        return await when_save_directory_without_csrf_header(api)
    if step in {"storage", "storage-test"}:
        return await when_save_storage_without_csrf_header(api, test=step == "storage-test")
    return await when_set_up_admin_without_csrf_header(api)


async def when_password_is_submitted_in_every_setup_outcome(
    api: Api, *, login_id: str, password: str
) -> list[Response]:
    """같은 비밀번호로 오답(접미사)·너무 긴 값·정답을 차례로 최초 설정에 낸다."""
    return [
        await when_set_up_admin(api, login_id=login_id, password=password + "x"),
        await when_set_up_admin(api, login_id=login_id, password=password * 20),
        await when_set_up_admin(api, login_id=login_id, password=password),
    ]


# ---- Then ----


def then_setup_is_closed(response: Response) -> None:
    """최초 admin이 이미 있어 설정이 닫혀 있다: 409 invalid-state, 안내 문구, 세션 쿠키 없음."""
    assert response.status_code == 409, response.text
    assert str(response.json()["type"]).endswith("invalid-state")
    assert response.json()["detail"] == SETUP_CLOSED
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")


def then_directory_must_be_saved_first(response: Response) -> None:
    assert response.status_code == 409, response.text
    assert str(response.json()["type"]).endswith("invalid-state")
    assert response.json()["detail"] == DIRECTORY_FIRST


def then_validation_error_names_field(response: Response, field: str) -> None:
    """422 Problem이고 오류 본문이 문제의 필드 이름을 가리킨다."""
    body = response.json()
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert str(body["type"]).rsplit("/", 1)[-1] in {"invalid-value", "request-validation"}
    assert field in json.dumps(body, ensure_ascii=False)


def then_no_response_mentions(responses: list[Response], *fragments: str) -> None:
    """어떤 응답에도 내부 정보 조각(예: 비밀번호)이 드러나지 않는다."""
    for response in responses:
        then_response_does_not_mention(response, *fragments)


async def when_read_auth_config(api: Api) -> Response:
    return await api.get(CONFIG)


def then_directory_probe_count_is(api: Api, expected: int) -> None:
    assert probe_count(api) == expected


async def then_user_is_not_registered(api: Api, *, login_id: str) -> None:
    rows = await sql_rows(
        api, "select count(*) from users where lower(login_id) = :login_id", login_id=login_id
    )
    assert rows == [(0,)]
