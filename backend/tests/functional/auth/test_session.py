"""Feature: 로그인한 사원만 업무 API를 쓰고, 로그아웃·삭제·역할 변경이 다음 요청부터 반영된다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import CONFIG, ME, USERS, given_logged_in_as
from tests.functional.steps.common import (
    then_body_is,
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.login import (
    given_employee,
    given_employee_deleted,
    when_log_in,
)
from tests.functional.steps.login_db import (
    given_employee_removed_from_database,
    given_role_changed_in_database,
    given_session_expired,
)
from tests.functional.steps.requests import (
    when_get,
    when_request,
    when_request_without_csrf_header,
)
from tests.functional.steps.rereads import then_login_still_fails, then_token_is_rejected
from tests.functional.steps.session import (
    given_session_token,
    given_session_works,
    session_cookie_header,
    then_caller_is_anonymous,
    when_get_me,
    when_get_with_session,
    when_log_out,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api
    from tests.functional.steps.auth import RoleName

pytestmark = pytest.mark.integration

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"
UNKNOWN_TOKEN = "made-up-token"  # noqa: S105 - 서버가 발급한 적 없는 더미 토큰
CONTACTS = "/api/v1/contacts"
PROTECTED = [
    CONTACTS,
    f"{CONTACTS}/companies",
    "/api/v1/deals",
    "/api/v1/deals/pipeline",
    f"/api/v1/deals/{UNKNOWN_ID}/stage-changes",
    "/api/v1/deals/20261016-A001/actions",
    ME,
]
PROTECTED_WRITES = [
    ("POST", CONTACTS, {}),
    ("DELETE", f"/api/v1/deals/{UNKNOWN_ID}", None),
    ("POST", f"/api/v1/deals/{UNKNOWN_ID}/stage", {"stage": "introduction"}),
]
ROLES = ["admin", "sales", "user"]


@pytest.mark.parametrize("path", PROTECTED)
async def test_protected_endpoints_require_a_session(api: Api, path: str) -> None:
    """Scenario: 로그인하지 않고 보호된 조회 API를 부르면 401 unauthenticated이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_get(api, path)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_WRITES)
async def test_write_endpoints_are_protected_too(
    api: Api, method: str, path: str, body: dict[str, object] | None
) -> None:
    """Scenario: 로그인하지 않고 등록·삭제·단계 변경을 요청해도 401이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_request(api, method, path, json=body)
    # Then
    then_status_is(response, 401)


async def test_unknown_session_cookie_is_unauthenticated(api: Api) -> None:
    """Scenario: 서버가 발급한 적 없는 세션 쿠키는 인증되지 않는다."""
    # Given
    # (발급되지 않은 토큰)
    # When
    response = await when_get_with_session(api, CONTACTS, token=UNKNOWN_TOKEN)
    # Then
    then_status_is(response, 401)


async def test_expired_session_cookie_is_unauthenticated(api: Api) -> None:
    """Scenario: 유효 시간이 지난 세션 쿠키는 인증되지 않는다."""
    # Given
    await given_employee(api)
    token = await given_session_token(api, login_id="kim")
    await given_session_expired(api)
    # When
    response = await when_get_with_session(api, CONTACTS, token=token)
    # Then
    then_status_is(response, 401)


@pytest.mark.parametrize("path", ["/healthz", "/readyz", CONFIG])
async def test_health_and_auth_config_are_public(api: Api, path: str) -> None:
    """Scenario: 헬스체크와 인증 설정 조회는 로그인 없이 200이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_get(api, path)
    # Then
    then_status_is(response, 200)


async def test_auth_config_has_exactly_the_five_flags(api: Api) -> None:
    """Scenario: 인증 설정 응답은 다섯 개의 플래그(최초 설정 3단계 포함)만 담고 OIDC 항목이 없다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_get(api, CONFIG)
    # Then
    assert set(response.json()) == {
        "dev_login",
        "directory_login",
        "needs_directory_setup",
        "needs_storage_setup",
        "needs_admin_setup",
    }


async def test_me_returns_the_signed_in_user(api: Api) -> None:
    """Scenario: 내 정보는 로그인한 사원의 users 행 id와 주체 정보만 돌려준다."""
    # Given
    user_id = await given_employee(api)
    await when_log_in(api)
    # When
    response = await when_get_me(api)
    # Then
    then_body_is(
        response,
        {
            "user_id": user_id,
            "subject": "kim",
            "email": "kim@corp.test",
            "name": "김영업",
            "role": "sales",
        },
    )


@pytest.mark.parametrize("role", ROLES)
async def test_me_works_for_every_role(api: Api, role: RoleName) -> None:
    """Scenario: admin·sales·user 어느 역할로 로그인해도 내 정보에 그 역할이 나온다."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_get_me(api)
    # Then
    assert response.json()["role"] == role


async def test_read_requests_do_not_need_the_csrf_header(api: Api) -> None:
    """Scenario: CSRF 헤더가 없어도 조회 요청은 허용된다."""
    # Given
    await given_employee(api)
    await when_log_in(api)
    # When
    response = await when_request_without_csrf_header(
        api, "GET", f"{CONTACTS}/companies?kind=customer"
    )
    # Then
    then_status_is(response, 200)


async def test_unsafe_requests_need_the_csrf_header(api: Api) -> None:
    """Scenario: CSRF 헤더 없는 등록 요청은 로그인했어도 403 csrf이다."""
    # Given
    await given_employee(api)
    await when_log_in(api)
    # When
    response = await when_request_without_csrf_header(
        api, "POST", CONTACTS, json={"company_name": "a", "contact_name": "b"}
    )
    # Then
    then_problem_is(response, status=403, type_suffix="csrf")


async def test_user_registration_needs_the_csrf_header(api: Api) -> None:
    """Scenario: CSRF 헤더 없는 사용자 등록 요청은 admin이어도 403 csrf이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_request_without_csrf_header(
        api, "POST", USERS, json={"login_id": "newbie", "role": "user"}
    )
    # Then
    then_problem_is(response, status=403, type_suffix="csrf")


@pytest.mark.parametrize("role", ROLES)
async def test_logout_revokes_the_session_for_every_role(api: Api, role: RoleName) -> None:
    """Scenario: 로그아웃하면 쿠키가 만료되고 서버 세션도 끝나 이후 요청은 401이다."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_log_out(api)
    # Then
    then_status_is(response, 204)
    assert "max-age=0" in session_cookie_header(response).lower()
    await then_caller_is_anonymous(api)


async def test_logout_without_a_session_is_harmless(api: Api) -> None:
    """Scenario: 로그인하지 않은 채 로그아웃을 요청해도 204로 무해하다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_log_out(api)
    # Then
    then_status_is(response, 204)


async def test_deleted_users_session_is_rejected_from_the_next_request(api: Api) -> None:
    """Scenario: admin이 사원을 삭제하면 그 사원의 기존 세션은 다음 요청부터 401이다."""
    # Given
    user_id = await given_employee(api)
    token = await given_session_token(api, login_id="kim")
    await given_session_works(api, token=token)
    await given_employee_deleted(api, user_id=user_id)
    # When
    response = await when_get_with_session(api, CONTACTS, token=token)
    # Then
    then_status_is(response, 401)
    await then_token_is_rejected(api, ME, token=token)


async def test_session_of_a_user_removed_from_the_database_locks_the_user_out(api: Api) -> None:
    """Scenario: 사용자 행이 DB에서 사라지면 기존 세션이 401이고 다시 로그인할 수도 없다."""
    # Given
    await given_employee(api)
    token = await given_session_token(api, login_id="kim")
    await given_session_works(api, token=token)
    await given_employee_removed_from_database(api, login_id="kim")
    # When
    response = await when_get_with_session(api, CONTACTS, token=token)
    # Then
    then_status_is(response, 401)
    await then_token_is_rejected(api, ME, token=token)
    await then_login_still_fails(api, "kim")


async def test_role_change_in_the_database_applies_to_existing_sessions(api: Api) -> None:
    """Scenario: users 테이블의 역할이 바뀌면 이미 로그인한 세션에 즉시 반영된다."""
    # Given
    await given_employee(api)
    await when_log_in(api)
    await given_role_changed_in_database(api, login_id="kim", role="admin")
    # When
    response = await when_get_me(api)
    # Then
    assert response.json()["role"] == "admin"
