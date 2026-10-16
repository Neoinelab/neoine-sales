"""Feature: 설정 화면에 입력한 비밀번호는 응답·로그·DB 어디에도 남지 않는다."""

import logging
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.settings import (
    NEW_DN,
    SETTINGS,
    SETTINGS_TEST,
    given_admin_directory_password,
    probe_payload,
    update_payload,
)
from tests.functional.steps.settings_secrecy import (
    then_no_table_holds_the_passwords,
    when_admin_saves_and_tests_with_wrong_and_right_passwords,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import Response

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
SECRET = "S3cret-Dummy-pw!"  # noqa: S105 - 가짜 값. 응답·로그·DB 누출 검사에 쓴다
LONG_PASSWORD = "p" * 300
TABLES = ("users", "login_failures", "directory_settings", "auth_sessions")

REQUESTS: dict[str, tuple[int, Callable[[Api], Awaitable[Response]]]] = {
    "save-ok": (200, lambda api: api.put(SETTINGS, json=update_payload(password=SECRET))),
    "save-wrong-password": (
        422,
        lambda api: api.put(SETTINGS, json=update_payload(password="x" + SECRET)),
    ),
    "save-too-long-password": (
        422,
        lambda api: api.put(SETTINGS, json=update_payload(password=LONG_PASSWORD)),
    ),
    "save-stale-revision": (
        409,
        lambda api: api.put(SETTINGS, json=update_payload(9, password=SECRET)),
    ),
    "test-ok": (200, lambda api: api.post(SETTINGS_TEST, json=probe_payload(password=SECRET))),
    "test-wrong-password": (
        200,
        lambda api: api.post(SETTINGS_TEST, json=probe_payload(password="x" + SECRET)),
    ),
    "test-too-long-password": (
        422,
        lambda api: api.post(SETTINGS_TEST, json=probe_payload(password=LONG_PASSWORD)),
    ),
    "read": (200, lambda api: api.get(SETTINGS)),
}


@pytest.mark.parametrize("case", list(REQUESTS))
async def test_settings_responses_and_errors_never_echo_the_password(
    api: Api, caplog: pytest.LogCaptureFixture, case: str
) -> None:
    """Scenario: 저장·연결 테스트·조회의 성공·오류 응답과 로그에 입력한 비밀번호가 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_admin_directory_password(api, SECRET)
    caplog.set_level(logging.DEBUG)
    expected_status, send = REQUESTS[case]
    # When
    response = await send(api)
    # Then
    then_status_is(response, expected_status)
    assert SECRET not in response.text
    assert LONG_PASSWORD not in response.text
    assert SECRET not in "".join(response.headers.values())
    body = response.json()
    assert not any("password" in key.lower() for key in body)
    assert all("input" not in err for err in body.get("errors") or [])
    assert SECRET not in caplog.text
    assert LONG_PASSWORD not in caplog.text


async def test_settings_changes_leave_no_password_in_any_table(api: Api) -> None:
    """Scenario: 설정 저장·연결 테스트(성공·실패)를 해도 어떤 테이블에도 비밀번호가 남지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_admin_directory_password(api, SECRET)
    wrong = SECRET + "-wrong"
    # When
    await when_admin_saves_and_tests_with_wrong_and_right_passwords(
        api, right=SECRET, wrong=wrong, base_dn=NEW_DN
    )
    # Then
    await then_no_table_holds_the_passwords(
        api, TABLES, passwords=[SECRET, wrong], saved_base_dn=NEW_DN
    )
