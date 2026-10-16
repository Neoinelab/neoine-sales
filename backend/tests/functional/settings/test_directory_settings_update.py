"""Feature: admin은 자기 비밀번호로 확인한 뒤 AD 연결 설정을 저장하고, 잘못된 저장은 거부된다."""

from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.rereads import then_settings_equal
from tests.functional.steps.settings import (
    ADMIN_PASSWORD,
    NEW_DN,
    SETTINGS_FIELDS,
    STORED_DN,
    WRONG_PASSWORD,
    current_user_id,
    given_directory_fails_with,
    given_no_directory_calls_yet,
    given_settings_saved,
    then_directory_authenticated_once,
    then_directory_not_called,
    then_stored_revision_is,
    then_stored_settings_are,
    then_updated_by_is_user_ref,
    update_payload,
    when_update_settings,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
PROBLEM_FAILED = ("directory-verification-failed",)


async def test_admin_updates_settings_after_verifying_with_their_own_password(api: Api) -> None:
    """Scenario: admin이 자기 비밀번호로 저장하면 새 설정이 저장되고 저장한 사람이 기록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(base_dn=NEW_DN))
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == SETTINGS_FIELDS
    assert (body["base_dn"], body["revision"]) == (NEW_DN, 2)
    then_updated_by_is_user_ref(body, user_id=await current_user_id(api), name="관리자")
    await then_settings_equal(api, body)
    then_directory_authenticated_once(api, login_id="root", password=ADMIN_PASSWORD, base_dn=NEW_DN)


async def test_each_save_bumps_the_revision(api: Api) -> None:
    """Scenario: 저장할 때마다 개정 번호가 하나씩 오른다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_settings_saved(api, expected_revision=1, base_dn="dc=a,dc=t")
    # When
    response = await when_update_settings(api, update_payload(2, base_dn="dc=b,dc=t"))
    # Then
    then_status_is(response, 200)
    assert response.json()["revision"] == 3
    await then_stored_revision_is(api, 3)


async def test_update_with_the_wrong_password_is_422_and_keeps_the_old_settings(api: Api) -> None:
    """Scenario: 틀린 비밀번호 저장은 bind 단계 422이고 응답에 비밀번호가 없으며 설정은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_settings(
        api, update_payload(password=WRONG_PASSWORD, base_dn=NEW_DN)
    )
    # Then
    then_problem_kind_is(response, status=422, kinds=PROBLEM_FAILED)
    assert response.json()["stage"] == "bind"
    assert WRONG_PASSWORD not in response.text
    await then_stored_settings_are(api, revision=1, base_dn=STORED_DN)


@pytest.mark.parametrize(
    ("error", "stage"),
    [
        (DirectoryUnavailableError(stage=VerificationStage.CONNECT), "connect"),
        (DirectoryUnavailableError(stage=VerificationStage.TLS), "tls"),
        (DirectoryMisconfiguredError(stage=VerificationStage.SEARCH), "search"),
        (InvalidCredentialsError(stage=VerificationStage.BIND), "bind"),
    ],
)
async def test_update_verification_failure_is_422_with_the_failed_stage(
    api: Api, error: Exception, stage: str
) -> None:
    """Scenario: AD 검증이 단계별로 실패하면 422이고 실패한 단계를 알려 주며 저장하지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_directory_fails_with(api, error)  # type: ignore[arg-type]
    # When
    response = await when_update_settings(api, update_payload(base_dn=NEW_DN))
    # Then
    then_problem_kind_is(response, status=422, kinds=PROBLEM_FAILED)
    assert response.json()["stage"] == stage
    assert response.json()["detail"]
    await then_stored_revision_is(api, 1)


async def test_update_with_a_stale_revision_is_409_without_calling_the_directory(api: Api) -> None:
    """Scenario: 이미 바뀐 개정 번호로 저장하면 409(invalid-state)이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_settings_saved(api, expected_revision=1, base_dn="dc=a,dc=t")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(1, base_dn=NEW_DN))
    # Then
    then_problem_kind_is(response, status=409, kinds=("invalid-state",))
    then_directory_not_called(api)
    await then_stored_settings_are(api, revision=2, base_dn="dc=a,dc=t")


async def test_update_without_a_password_is_422_invalid_value_and_skips_the_directory(
    api: Api,
) -> None:
    """Scenario: 비밀번호 없이 저장하면 422(invalid-value)이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(password=None))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    then_directory_not_called(api)


@pytest.mark.parametrize("password", ["", "   ", "pw\x00x", "p" * 257])
async def test_update_with_an_unusable_password_is_422_and_skips_the_directory(
    api: Api, password: str
) -> None:
    """Scenario: 비어 있거나 NUL을 품거나 너무 긴 비밀번호는 422이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(password=password, base_dn=NEW_DN))
    # Then
    then_status_is(response, 422)
    assert api.directory.authenticate_calls == []
    await then_stored_revision_is(api, 1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"server_urls": []},
        {"server_urls": ["ldap://dc1.corp.test"], "use_starttls": False},
        {"server_urls": ["http://dc1.corp.test"]},
        {"bind_template": "no-placeholder"},
        {"connect_timeout_seconds": 0},
        {"receive_timeout_seconds": 61},
        {"ca_cert_pem": "not a pem"},
    ],
)
async def test_update_with_invalid_settings_is_422_and_changes_nothing(
    api: Api, overrides: dict[str, Any]
) -> None:
    """Scenario: 형식이 틀린 연결 설정은 422이고 AD를 부르지 않으며 아무것도 바뀌지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(**overrides))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value", "request-validation"))
    assert api.directory.authenticate_calls == []
    await then_stored_revision_is(api, 1)


def _drop_revision(payload: dict[str, Any]) -> None:
    payload.pop("expected_revision")


def _zero_revision(payload: dict[str, Any]) -> None:
    payload.update(expected_revision=0)


def _string_revision(payload: dict[str, Any]) -> None:
    payload.update(expected_revision="1")


def _unknown_field(payload: dict[str, Any]) -> None:
    payload.update(unknown_field=1)


def _drop_base_dn(payload: dict[str, Any]) -> None:
    payload.pop("base_dn")


@pytest.mark.parametrize(
    "mutate",
    [_drop_revision, _zero_revision, _string_revision, _unknown_field, _drop_base_dn],
)
async def test_update_with_a_malformed_body_is_422_request_validation(
    api: Api, mutate: Callable[[dict[str, Any]], None]
) -> None:
    """Scenario: 필수 필드 누락·타입 오류·모르는 필드는 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="admin")
    payload = update_payload()
    mutate(payload)
    # When
    response = await when_update_settings(api, payload)
    # Then
    then_problem_kind_is(response, status=422, kinds=("request-validation",))
