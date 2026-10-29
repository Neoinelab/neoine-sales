"""Feature: admin은 자기 비밀번호로 확인한 뒤 AD 연결 설정을 저장하고, 잘못된 저장은 거부된다.

서버는 서비스 계정으로 Base DN을 찾아 저장하고(입력 없음), 바인드 비밀번호는 암호화해 저장한다.
바인드 비밀번호를 비우면 저장된 값을 쓰되 서버·바인드 계정을 바꾸면 다시 입력해야 한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from tests.factories_auth import BIND_PASSWORD
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.rereads import then_settings_equal
from tests.functional.steps.settings import (
    ADMIN_PASSWORD,
    NEW_BIND_PASSWORD,
    NEW_DN,
    SETTINGS_FIELDS,
    STORED_DN,
    WRONG_PASSWORD,
    current_user_id,
    directory_error,
    given_directory_discovery_fails_with,
    given_directory_fails_with,
    given_directory_reports_base_dn,
    given_no_directory_calls_yet,
    given_settings_saved,
    then_directory_authenticated_once,
    then_directory_not_called,
    then_directory_used_bind_password,
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
    """Scenario: admin이 자기 비밀번호로 저장하면 새 설정과 Base DN이 저장되고 저장자가 기록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_directory_reports_base_dn(api, NEW_DN)
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(connect_timeout_seconds=9))
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == SETTINGS_FIELDS
    assert (body["base_dn"], body["revision"], body["connect_timeout_seconds"]) == (NEW_DN, 2, 9)
    then_updated_by_is_user_ref(body, user_id=await current_user_id(api), name="관리자")
    await then_settings_equal(api, body)
    then_directory_authenticated_once(api, login_id="root", password=ADMIN_PASSWORD, base_dn=NEW_DN)


async def test_each_save_bumps_the_revision(api: Api) -> None:
    """Scenario: 저장할 때마다 개정 번호가 하나씩 오른다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_settings_saved(api, expected_revision=1, base_dn="dc=a,dc=t")
    # When
    response = await when_update_settings(api, update_payload(2, connect_timeout_seconds=8))
    # Then
    then_status_is(response, 200)
    assert response.json()["revision"] == 3
    await then_stored_revision_is(api, 3)


async def test_update_with_the_wrong_password_is_422_and_keeps_the_old_settings(api: Api) -> None:
    """Scenario: 틀린 비밀번호 저장은 bind 단계 422이고 응답에 비밀번호가 없으며 설정은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_directory_reports_base_dn(api, NEW_DN)
    # When
    response = await when_update_settings(api, update_payload(password=WRONG_PASSWORD))
    # Then
    then_problem_kind_is(response, status=422, kinds=PROBLEM_FAILED)
    assert response.json()["stage"] == "bind"
    assert WRONG_PASSWORD not in response.text
    await then_stored_settings_are(api, revision=1, base_dn=STORED_DN)


@pytest.mark.parametrize(
    ("discovery", "kind", "stage"),
    [
        (True, "unavailable", "connect"),
        (True, "unavailable", "tls"),
        (True, "misconfigured", "service_bind"),
        (True, "misconfigured", "base_dn"),
        (False, "misconfigured", "search"),
        (False, "invalid", "search"),
        (False, "invalid", "bind"),
    ],
)
async def test_update_verification_failure_is_422_with_the_failed_stage(
    api: Api, discovery: bool, kind: str, stage: str
) -> None:
    """Scenario: 확인이 단계별로 실패하면 422이고 실패한 단계를 알려 주며 저장하지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    error = directory_error(kind, stage)
    if discovery:
        given_directory_discovery_fails_with(api, error)
    else:
        given_directory_fails_with(api, error)
    # When
    response = await when_update_settings(api, update_payload(connect_timeout_seconds=9))
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
    response = await when_update_settings(api, update_payload(1, connect_timeout_seconds=9))
    # Then
    then_problem_kind_is(response, status=409, kinds=("invalid-state",))
    then_directory_not_called(api)
    await then_stored_settings_are(api, revision=2, base_dn="dc=a,dc=t")


async def test_update_without_a_password_is_422_invalid_value_and_skips_the_admin_bind(
    api: Api,
) -> None:
    """Scenario: admin 비밀번호 없이 저장하면 422(invalid-value)이고 admin 바인드를 하지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(password=None))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    assert api.directory.authenticate_calls == []
    await then_stored_revision_is(api, 1)


@pytest.mark.parametrize("password", ["", "   ", "pw\x00x", "p" * 257])
async def test_update_with_an_unusable_password_is_422_and_skips_the_directory(
    api: Api, password: str
) -> None:
    """Scenario: 비어 있거나 NUL을 품거나 너무 긴 admin 비밀번호는 422이고 AD를 부르지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(password=password))
    # Then
    then_status_is(response, 422)
    assert api.directory.authenticate_calls == []
    await then_stored_revision_is(api, 1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"host": "ldaps://dc1.corp.test"},
        {"host": "dc1.corp.test:636"},
        {"port": 0},
        {"port": 65536},
        {"bind_account": ""},
        {"bind_account": "x" * 257},
        {"user_filter": "no-placeholder"},
        {"connect_timeout_seconds": 0},
        {"connect_timeout_seconds": 31},
        {"security": "tls"},
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
    response = await when_update_settings(
        api, update_payload(bind_password=NEW_BIND_PASSWORD, **overrides)
    )
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value", "request-validation"))
    then_directory_not_called(api)
    await then_stored_revision_is(api, 1)


@pytest.mark.parametrize(
    "old_field",
    [
        "server_urls",
        "use_starttls",
        "ca_cert_pem",
        "bind_template",
        "base_dn",
        "display_name_attribute",
        "email_attribute",
        "receive_timeout_seconds",
    ],
)
async def test_update_with_a_removed_field_is_422_request_validation(
    api: Api, old_field: str
) -> None:
    """Scenario: 폐지된 구 필드(Base DN 입력 포함)를 보내면 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    payload = {**update_payload(), old_field: "x"}
    # When
    response = await when_update_settings(api, payload)
    # Then
    then_problem_kind_is(response, status=422, kinds=("request-validation",))
    then_directory_not_called(api)


def _drop_revision(payload: dict[str, Any]) -> None:
    payload.pop("expected_revision")


def _zero_revision(payload: dict[str, Any]) -> None:
    payload.update(expected_revision=0)


def _string_revision(payload: dict[str, Any]) -> None:
    payload.update(expected_revision="1")


def _unknown_field(payload: dict[str, Any]) -> None:
    payload.update(unknown_field=1)


def _drop_host(payload: dict[str, Any]) -> None:
    payload.pop("host")


@pytest.mark.parametrize(
    "mutate",
    [_drop_revision, _zero_revision, _string_revision, _unknown_field, _drop_host],
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


async def test_admin_saves_without_retyping_bind_password(api: Api) -> None:
    """Scenario: bind_password를 생략하면 저장된 비밀번호로 확인하고 비밀번호는 그대로 유지된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(
        api, update_payload(connect_timeout_seconds=9, user_filter="(uid={login_id})")
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["bind_credential_status"] == "ok"
    then_directory_used_bind_password(api, BIND_PASSWORD)


async def test_admin_saves_with_an_explicit_null_bind_password_as_keep(api: Api) -> None:
    """Scenario: bind_password를 null로 보내도 생략과 같게 저장된 비밀번호를 쓴다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_settings(
        api, update_payload(bind_password=None, connect_timeout_seconds=9)
    )
    # Then
    then_status_is(response, 200)
    then_directory_used_bind_password(api, BIND_PASSWORD)


@pytest.mark.parametrize(
    "change",
    [
        {"host": "dc2.corp.test"},
        {"port": 3269},
        {"security": "starttls"},
        {"bind_account": "cn=other,ou=services,dc=corp,dc=test"},
    ],
    ids=["host", "port", "security", "bind_account"],
)
async def test_changing_an_endpoint_field_without_bind_password_is_rejected(
    api: Api, change: dict[str, Any]
) -> None:
    """Scenario: 호스트·포트·보안 연결·바인드 계정을 바꾸고 비밀번호를 생략하면 422이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(**change))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    assert "bind_password" in response.text
    assert "다시 입력" in response.text
    then_directory_not_called(api)
    await then_stored_revision_is(api, 1)


async def test_admin_saves_with_new_bind_password(api: Api) -> None:
    """Scenario: 새 바인드 비밀번호를 보내면 그 값으로 확인하고 교체해 저장한다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_settings(
        api, update_payload(host="dc2.corp.test", bind_password=NEW_BIND_PASSWORD)
    )
    # Then
    then_status_is(response, 200)
    assert (response.json()["host"], response.json()["revision"]) == ("dc2.corp.test", 2)
    then_directory_used_bind_password(api, NEW_BIND_PASSWORD)
    assert NEW_BIND_PASSWORD not in response.text


@pytest.mark.parametrize("bind_password", ["", "   ", "pw\x00x", "p" * 257])
async def test_unusable_bind_password_is_rejected(api: Api, bind_password: str) -> None:
    """Scenario: 빈 문자열은 '유지'가 아니라 값 위반이다(공백·NUL·너무 긴 값도 422)."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_no_directory_calls_yet(api)
    # When
    response = await when_update_settings(api, update_payload(bind_password=bind_password))
    # Then
    then_problem_kind_is(response, status=422, kinds=("invalid-value",))
    assert "bind_password" in response.text
    then_directory_not_called(api)
    await then_stored_revision_is(api, 1)
