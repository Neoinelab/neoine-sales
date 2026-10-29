"""Feature: 로그인에 실패하면 원인을 알 수 없는 공통 응답을 받고 비밀번호는 노출되지 않는다."""

import json
from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from tests.functional.steps.auth import given_ad_account, password_of
from tests.functional.steps.common import (
    then_body_includes,
    then_problem_is,
    then_response_does_not_mention,
    then_status_is,
)
from tests.functional.steps.login import (
    credentials,
    directory_call_count,
    given_employee,
    given_employee_deleted,
    then_directory_was_not_asked_again,
    then_failure_count_is,
    then_login_failed_with_the_common_401,
    then_no_cookie_is_set,
    when_log_in,
    when_log_in_during_each_outage,
    when_log_in_without_csrf_header,
    when_post_login_body,
    when_submit_password_in_every_outcome,
)
from tests.functional.steps.requests import then_no_response_mentions, when_get
from tests.functional.steps.session import then_caller_is_anonymous
from tests.support.auth_seed import DUMMY_PASSWORD

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

LEAK = "ldap-server-internal-detail"
EMPTY_OR_NUL_PASSWORDS = ["", "   ", "pw\u0000x"]
OUTAGES = [
    DirectoryUnavailableError(LEAK, stage=VerificationStage.CONNECT),
    DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS),
    DirectoryMisconfiguredError(LEAK, stage=VerificationStage.SEARCH),
]


@pytest.mark.parametrize(
    "attempt",
    [
        credentials("kim", "wrong-password"),
        credentials("ghost", "pw-ghost"),
        credentials("newbie", "pw-newbie"),
        credentials("kim)(uid=*", "pw-kim"),
        credentials("kim", ""),
        credentials("kim", "   "),
        credentials("kim", "pw\u0000kim"),
    ],
    ids=["wrong", "not-in-ad", "unregistered", "malformed-id", "empty", "blank", "nul"],
)
async def test_every_failure_gets_the_same_401_without_cookie(
    api: Api, attempt: dict[str, str]
) -> None:
    """Scenario: 비밀번호 오류·AD에 없음·미등록·형식 오류·빈/NUL 비밀번호가 모두 같은 401이다."""
    # Given
    await given_employee(api)
    given_ad_account(api, login_id="newbie")
    # When
    response = await when_post_login_body(api, attempt)
    # Then
    then_login_failed_with_the_common_401(response)
    await then_caller_is_anonymous(api)


async def test_deleted_employee_gets_the_same_401(api: Api) -> None:
    """Scenario: 삭제된 사원이 로그인하면 다른 실패와 같은 공통 401을 받는다."""
    # Given
    gone_id = await given_employee(api, login_id="gone")
    await given_employee_deleted(api, user_id=gone_id)
    # When
    response = await when_log_in(api, login_id="gone")
    # Then
    then_login_failed_with_the_common_401(response)


@pytest.mark.parametrize("password", EMPTY_OR_NUL_PASSWORDS)
async def test_empty_or_nul_password_never_reaches_the_directory(api: Api, password: str) -> None:
    """Scenario: 빈 값·공백·NUL이 든 비밀번호는 AD에 전달되지 않고 401로 끝난다."""
    # Given
    await given_employee(api)
    calls_before = directory_call_count(api)
    # When
    response = await when_log_in(api, password=password)
    # Then
    then_status_is(response, 401)
    then_directory_was_not_asked_again(api, calls_before=calls_before)


@pytest.mark.parametrize("error", OUTAGES, ids=["connect", "tls", "misconfigured"])
async def test_directory_outage_is_503_with_a_fixed_message(
    api: Api, error: DirectoryUnavailableError
) -> None:
    """Scenario: AD 장애 중 대체 로그인도 못 하면 원인 문구를 숨긴 503이고 세션 쿠키가 없다."""
    # Given
    await given_employee(api)
    api.directory.authenticate_fails_with = error
    # When
    response = await when_log_in(api)
    # Then
    then_problem_is(response, status=503, type_suffix="directory-unavailable")
    then_response_does_not_mention(response, LEAK)
    then_no_cookie_is_set(response)
    assert response.json()["detail"]


async def test_directory_outage_message_is_identical_for_every_cause(api: Api) -> None:
    """Scenario: AD 장애 원인이 달라도 사용자에게 보이는 안내 문구는 같다."""
    # Given
    await given_employee(api)
    # When
    responses = await when_log_in_during_each_outage(api, OUTAGES)
    # Then
    assert len({response.json()["detail"] for response in responses}) == 1


async def test_login_before_directory_setup_is_409_without_asking_the_directory(api: Api) -> None:
    """Scenario: AD 연결 설정 전에 해시 없는 사용자가 로그인하면 409이고 AD를 호출하지 않는다."""
    # Given
    given_ad_account(api, login_id="kim")
    calls_before = directory_call_count(api)
    # When
    response = await when_log_in(api)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_body_includes(response, detail=DIRECTORY_NOT_CONFIGURED)
    then_directory_was_not_asked_again(api, calls_before=calls_before)


async def test_login_needs_the_csrf_header(api: Api) -> None:
    """Scenario: CSRF 헤더 없는 로그인 요청은 403이고 AD를 호출하지 않는다."""
    # Given
    await given_employee(api)
    calls_before = directory_call_count(api)
    # When
    response = await when_log_in_without_csrf_header(api)
    # Then
    then_problem_is(response, status=403, type_suffix="csrf")
    then_directory_was_not_asked_again(api, calls_before=calls_before)


@pytest.mark.parametrize(
    "body",
    [{}, {"login_id": "kim"}, {"password": "x"}, {**credentials(), "role": "admin"}],
    ids=["empty", "no-password", "no-login-id", "extra-field"],
)
async def test_malformed_login_bodies_are_422(api: Api, body: dict[str, str]) -> None:
    """Scenario: 필드가 빠졌거나 모르는 필드가 있는 로그인 본문은 422 request-validation이다."""
    # Given
    await given_employee(api)
    # When
    response = await when_post_login_body(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("field", ["password", "login_id"])
async def test_oversized_inputs_are_422_without_echoing_the_value(api: Api, field: str) -> None:
    """Scenario: 너무 긴 비밀번호·아이디는 422이고 입력값을 응답에 되돌려주지 않는다."""
    # Given
    await given_employee(api)
    oversized = {"password": DUMMY_PASSWORD + "p" * 300, "login_id": "i" * 300}
    body = credentials("kim", "pw-kim") | {field: oversized[field]}
    # When
    response = await when_post_login_body(api, body)
    # Then
    then_status_is(response, 422)
    then_response_does_not_mention(response, oversized[field], DUMMY_PASSWORD)
    assert "input" not in json.dumps(response.json()["errors"])


@pytest.mark.parametrize(
    ("path", "allowed"),
    [("/api/v1/auth/login", {404, 405}), ("/api/v1/auth/callback", {404})],
    ids=["login-get", "oidc-callback"],
)
async def test_legacy_oidc_routes_do_not_exist(api: Api, path: str, allowed: set[int]) -> None:
    """Scenario: 폐지된 OIDC 경로는 없는 경로이고 어디로도 리다이렉트하지 않는다."""
    # Given
    await given_employee(api)
    # When
    response = await when_get(api, path, params={"code": "c"})
    # Then
    assert response.status_code in allowed
    assert "location" not in response.headers


async def test_password_never_appears_in_responses_or_logs(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: 성공·실패·검증 오류·AD 장애(대체 로그인 성공·실패) 어디에도 비밀번호가 없다."""
    # Given
    caplog.set_level("DEBUG")
    await given_employee(api)
    await given_employee(api, login_id="lee", display_name="이영업", email="lee@corp.test")
    api.directory.add_account("kim", DUMMY_PASSWORD)
    api.directory.add_account("lee", DUMMY_PASSWORD)
    # When
    responses = await when_submit_password_in_every_outcome(api, DUMMY_PASSWORD)
    # Then
    assert [r.status_code for r in responses] == [200, 401, 422, 200, 503]
    then_no_response_mentions(responses, DUMMY_PASSWORD)
    assert DUMMY_PASSWORD not in caplog.text


async def test_user_missing_in_directory_gets_401_and_counts_failure(api: Api) -> None:
    """Scenario: AD 검색에 사용자가 없으면 공통 401이고 실패 1회로 센다(대체 로그인 없음)."""
    # Given
    await given_employee(api, login_id="kim")
    await when_log_in(api)  # 성공해 해시가 생긴다
    api.directory.authenticate_fails_with = InvalidCredentialsError(stage=VerificationStage.SEARCH)
    # When
    response = await when_log_in(api)
    # Then
    then_login_failed_with_the_common_401(response)
    then_no_cookie_is_set(response)
    await then_failure_count_is(api, 1)


async def test_wrong_password_gets_401_even_with_stored_hash(api: Api) -> None:
    """Scenario: AD가 비밀번호를 바꿔 거부하면 저장된 예전 비밀번호 해시가 맞아도 401이다."""
    # Given
    await given_employee(api)
    old_password = password_of("kim")
    assert (await when_log_in(api, password=old_password)).status_code == 200
    api.directory.add_account("kim", "changed-in-directory-1!")  # AD에서 비밀번호가 바뀌었다
    # When
    response = await when_log_in(api, password=old_password)
    # Then
    then_login_failed_with_the_common_401(response)
    then_no_cookie_is_set(response)
    await then_failure_count_is(api, 1)
