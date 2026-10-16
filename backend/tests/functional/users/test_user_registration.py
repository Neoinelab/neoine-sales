"""Feature: admin은 AD 계정 아이디와 역할로 사용자를 등록한다(중복·형식 오류는 거절된다)."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import USERS, given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.requests import when_request_without_csrf_header
from tests.functional.steps.users import (
    USER_KEYS,
    USER_REF_KEYS,
    capture_session,
    directory_calls,
    given_user_deleted,
    id_of,
    then_directory_untouched_since,
    then_is_scenario_now,
    then_logins_listed,
    then_problem_type_is_one_of,
    when_register_user,
    when_register_with_body,
    when_request_as,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
SOME_ID = "6f1c1b3a-0000-4000-8000-000000000001"


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_register_user_returns_201_with_the_chosen_role(api: Api, role: str) -> None:
    """Scenario: 선택한 역할로 등록하면 201과 문서화된 필드가 돌아오고 목록 끝에 추가된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id="new.hire", role=role)
    # Then
    then_status_is(response, 201)
    body = response.json()
    assert set(body) == USER_KEYS
    assert (body["login_id"], body["role"]) == ("new.hire", role)
    assert set(body["created_by"]) == USER_REF_KEYS
    assert body["created_by"]["label"] == body["created_by"]["name"]  # 재직 중인 등록자
    assert body["created_by"]["resigned"] is False
    assert (body["status"], body["deleted_at"], body["delete_reason"]) == ("active", None, None)
    assert body["last_login_at"] is None
    then_is_scenario_now(body["created_at"])
    await then_logins_listed(api, ["root", "new.hire"])


async def test_register_user_normalizes_the_login_id(api: Api) -> None:
    """Scenario: 앞뒤 공백과 대소문자는 정규화(소문자·trim)되어 저장된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id="  Kim.Lee ", role="user")
    # Then
    then_status_is(response, 201)
    assert response.json()["login_id"] == "kim.lee"


async def test_register_user_does_not_check_the_directory(api: Api) -> None:
    """Scenario: 등록은 AD에 묻지 않는다(AD에 없는 계정도 등록되고 AD 호출이 늘지 않는다)."""
    # Given
    await given_logged_in_as(api, role="admin")
    baseline = directory_calls(api)
    # When
    response = await when_register_user(api, login_id="not-in-ad", role="sales")
    # Then
    then_status_is(response, 201)
    then_directory_untouched_since(api, baseline)


@pytest.mark.parametrize("duplicate", ["root", "ROOT", " root "])
async def test_register_user_with_an_active_login_id_is_409_already_exists(
    api: Api, duplicate: str
) -> None:
    """Scenario: 재직 중인 아이디는 대소문자·공백이 달라도 409 중복이고 목록은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id=duplicate, role="user")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    await then_logins_listed(api, ["root"])


async def test_register_user_again_after_a_physical_deletion_is_201(api: Api) -> None:
    """Scenario: 물리 삭제된 아이디는 다시 등록할 수 있고 새 id가 부여된다."""
    # Given
    kim_id = await given_user_registered(api, login_id="kim", role="sales")
    await given_user_deleted(api, kim_id)
    # When
    response = await when_register_user(api, login_id="kim", role="user")
    # Then
    then_status_is(response, 201)
    assert response.json()["id"] != kim_id
    await then_logins_listed(api, ["root", "kim"])


@pytest.mark.parametrize("reserved", ["dev-admin", "dev-sales", "dev-user"])
async def test_register_user_with_a_reserved_dev_login_id_is_422(api: Api, reserved: str) -> None:
    """Scenario: 개발 로그인 예약 아이디는 등록할 수 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id=reserved, role="user")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_logins_listed(api, ["root"])


@pytest.mark.parametrize("login_id", ["", "   ", "-lead", ".lead", "a b", "한글", "a,b", "a=b"])
async def test_register_user_with_a_malformed_login_id_is_422_invalid_value(
    api: Api, login_id: str
) -> None:
    """Scenario: 형식에 맞지 않는 아이디는 422이고 사용자가 만들어지지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id=login_id, role="user")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_logins_listed(api, ["root"])


async def test_register_user_with_a_65_character_login_id_is_422(api: Api) -> None:
    """Scenario: 65자 아이디는 길이 초과로 거절된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id="a" * 65, role="user")
    # Then
    then_problem_type_is_one_of(
        response, status=422, suffixes={"invalid-value", "request-validation"}
    )
    await then_logins_listed(api, ["root"])


async def test_register_user_accepts_a_64_character_login_id(api: Api) -> None:
    """Scenario: 64자 아이디는 경계값으로 등록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id="a" * 64, role="user")
    # Then
    then_status_is(response, 201)


@pytest.mark.parametrize(
    "body",
    [
        {"login_id": "kim"},
        {"role": "user"},
        {"login_id": "kim", "role": "superuser"},
        {"login_id": "kim", "role": None},
        {"login_id": 7, "role": "user"},
        {"login_id": "kim", "role": "user", "password": "pw"},
        {"login_id": "kim", "role": "user", "nickname": "김"},
        {},
    ],
)
async def test_register_user_with_a_bad_body_is_422_request_validation(
    api: Api, body: dict[str, object]
) -> None:
    """Scenario: 필수 값 누락·잘못된 역할·허용되지 않은 필드는 422 검증 오류다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_with_body(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_logins_listed(api, ["root"])


@pytest.mark.parametrize("method", ["put", "patch", "get", "post"])
async def test_there_is_no_user_update_or_read_one_endpoint(api: Api, method: str) -> None:
    """Scenario: 사용자 한 명을 읽거나 수정하는 API는 없다(405)."""
    # Given
    await given_logged_in_as(api, role="admin")
    session = await capture_session(api, "root")
    # When
    response = await when_request_as(
        api, session, method.upper(), f"{USERS}/{SOME_ID}", json={"role": "admin"}
    )
    # Then
    then_status_is(response, 405)


@pytest.mark.parametrize("method", ["POST", "DELETE"])
async def test_register_and_delete_require_the_csrf_header(api: Api, method: str) -> None:
    """Scenario: CSRF 헤더가 없으면 등록·삭제는 403 csrf로 거절된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim_id = await given_user_registered(api, login_id="kim", role="user")
    url = USERS if method == "POST" else f"{USERS}/{kim_id}"
    # When
    response = await when_request_without_csrf_header(
        api, method, url, json={"login_id": "lee", "role": "user"} if method == "POST" else None
    )
    # Then
    then_problem_is(response, status=403, type_suffix="csrf")
    await then_logins_listed(api, ["root", "kim"])
    assert await id_of(api, "kim") == kim_id
