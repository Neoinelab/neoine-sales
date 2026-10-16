"""Feature: 최초 설정의 잘못된 입력·AD 장애·반복 실패는 안전하게 거절되고 저장되지 않는다."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from tests.functional.steps.auth import (
    directory_payload,
    given_ad_account,
    given_setup_prerequisites_configured,
)
from tests.functional.steps.common import (
    then_problem_is,
    then_response_does_not_mention,
    then_status_is,
)
from tests.functional.steps.login import (
    ATTEMPT_LIMIT_PER_ACCOUNT,
    directory_call_count,
    then_auth_flags_are,
    then_directory_was_not_asked_again,
)
from tests.functional.steps.setup import (
    given_failed_setup_attempts,
    then_directory_probe_count_is,
    then_no_response_mentions,
    then_validation_error_names_field,
    when_password_is_submitted_in_every_setup_outcome,
    when_save_directory,
    when_save_directory_body,
    when_set_up_admin,
)
from tests.support.auth_seed import DUMMY_PASSWORD

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

LEAK = "internal-ldap-server-banner"
INVALID_DIRECTORY_SETTINGS = [
    ({"server_urls": ["http://dc1.corp.test"]}, "server_urls"),
    ({"server_urls": ["ldaps://dc1.corp.test/path"]}, "server_urls"),
    ({"server_urls": ["ldaps://dc1.corp.test:70000"]}, "server_urls"),
    ({"server_urls": ["ldaps://dc1.corp.test", "ldaps://dc1.corp.test:636"]}, "server_urls"),
    ({"server_urls": []}, "server_urls"),
    ({"server_urls": [f"ldaps://dc{n}.corp.test" for n in range(6)]}, "server_urls"),
    ({"server_urls": ["ldap://dc1.corp.test"], "use_starttls": False}, "use_starttls"),
    ({"bind_template": "cn=fixed,dc=corp"}, "bind_template"),
    ({"bind_template": "cn={login_id},cn={login_id}"}, "bind_template"),
    ({"user_filter": "sAMAccountName={login_id}"}, "user_filter"),
    ({"base_dn": ""}, "base_dn"),
    ({"display_name_attribute": "1bad"}, "display_name_attribute"),
    ({"email_attribute": "ma il"}, "email_attribute"),
    ({"ca_cert_pem": "not a pem"}, "ca_cert_pem"),
    ({"connect_timeout_seconds": 0}, "connect_timeout_seconds"),
    ({"connect_timeout_seconds": 31}, "connect_timeout_seconds"),
    ({"receive_timeout_seconds": 61}, "receive_timeout_seconds"),
]


@pytest.mark.parametrize(("override", "field"), INVALID_DIRECTORY_SETTINGS)
async def test_setup_directory_validation_errors_are_422_naming_the_field(
    api: Api, override: dict[str, object], field: str
) -> None:
    """Scenario: 잘못된 AD 설정 값은 422로 거절되고 문제의 필드를 알려주며 저장되지 않는다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_save_directory(api, **override)
    # Then
    then_validation_error_names_field(response, field)
    then_directory_probe_count_is(api, 0)
    await then_auth_flags_are(api, needs_directory=True, needs_storage=True, needs_admin=False)


async def test_setup_directory_rejects_unknown_fields(api: Api) -> None:
    """Scenario: 정의되지 않은 필드(bind_password 등)가 든 1단계 본문은 422이다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_save_directory_body(api, {**directory_payload(), "bind_password": "x"})
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize(
    "stage", [VerificationStage.CONNECT, VerificationStage.TLS], ids=["connect", "tls"]
)
async def test_setup_directory_probe_failure_is_422_with_only_the_coarse_stage(
    api: Api, stage: VerificationStage
) -> None:
    """Scenario: AD 연결 확인이 실패하면 422이고 대략적인 단계만 알려주며 저장되지 않는다."""
    # Given
    api.directory.probe_fails_with = DirectoryUnavailableError(LEAK, stage=stage)
    # When
    response = await when_save_directory(api)
    # Then
    then_problem_is(response, status=422, type_suffix="directory-verification-failed")
    assert response.json()["stage"] == stage.value
    then_response_does_not_mention(response, LEAK)
    await then_auth_flags_are(api, needs_directory=True, needs_storage=True, needs_admin=False)


@pytest.mark.parametrize("password", ["", "   ", "pw\u0000x"])
async def test_setup_admin_empty_password_never_reaches_the_directory(
    api: Api, password: str
) -> None:
    """Scenario: 빈 값·공백·NUL이 든 비밀번호는 AD에 전달되지 않고 401로 끝난다."""
    # Given
    await given_setup_prerequisites_configured(api)
    calls_before = directory_call_count(api)
    # When
    response = await when_set_up_admin(api, password=password)
    # Then
    then_status_is(response, 401)
    then_directory_was_not_asked_again(api, calls_before=calls_before)


async def test_setup_admin_directory_outage_is_503(api: Api) -> None:
    """Scenario: 최초 admin 확인 중 AD 장애는 원인 문구를 숨긴 503이다."""
    # Given
    await given_setup_prerequisites_configured(api)
    api.directory.fail_with = DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS)
    # When
    response = await when_set_up_admin(api)
    # Then
    then_problem_is(response, status=503, type_suffix="directory-unavailable")
    then_response_does_not_mention(response, LEAK)


async def test_setup_admin_is_throttled_with_429(api: Api) -> None:
    """Scenario: 최초 admin 지정이 5번 실패하면 올바른 비밀번호도 429이고 AD를 호출하지 않는다."""
    # Given
    await given_setup_prerequisites_configured(api)
    await given_failed_setup_attempts(api, login_id="kim", count=ATTEMPT_LIMIT_PER_ACCOUNT)
    given_ad_account(api, login_id="kim")
    calls_before = directory_call_count(api)
    # When
    response = await when_set_up_admin(api)
    # Then
    then_problem_is(response, status=429, type_suffix="too-many-attempts")
    then_directory_was_not_asked_again(api, calls_before=calls_before)


async def test_setup_never_echoes_or_logs_the_password(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: 최초 설정의 오답·검증 오류·성공 응답과 로그 어디에도 비밀번호가 없다."""
    # Given
    caplog.set_level("DEBUG")
    api.directory.add_account("kim", DUMMY_PASSWORD)
    await given_setup_prerequisites_configured(api)
    # When
    responses = await when_password_is_submitted_in_every_setup_outcome(
        api, login_id="kim", password=DUMMY_PASSWORD
    )
    # Then
    assert [r.status_code for r in responses] == [401, 422, 200]
    then_no_response_mentions(responses, DUMMY_PASSWORD)
    assert DUMMY_PASSWORD not in caplog.text
