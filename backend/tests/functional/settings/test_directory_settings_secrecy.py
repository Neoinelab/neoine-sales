"""Feature: 바인드 비밀번호와 admin 비밀번호는 응답·로그·DB 어디에도 평문으로 남지 않는다.

바인드 비밀번호는 `directory_settings.bind_password_encrypted`에 설정된 키로 암호화된 값으로만 있다.
암호문도 응답·헤더·로그에 나오지 않고, 응답 키 이름에 password가 들어가지 않는다.
"""

import logging
from typing import TYPE_CHECKING

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.factories_auth import BIND_PASSWORD
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.settings import (
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
from tests.support.crypto_keys import TEST_FERNET_KEY

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import Response

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
SECRET = "S3cret-Dummy-pw!"  # noqa: S105 - 가짜 값(admin 비밀번호). 응답·로그·DB 누출 검사에 쓴다
BIND_SECRET = "Bind-Dummy-pw-77!"  # noqa: S105 - 가짜 값(새 바인드 비밀번호)
LONG_PASSWORD = "p" * 300
TABLES = (
    "users",
    "login_failures",
    "directory_settings",
    "auth_sessions",
    "user_password_hashes",
)

REQUESTS: dict[str, tuple[int, Callable[[Api], Awaitable[Response]]]] = {
    "save-ok": (
        200,
        lambda api: api.put(
            SETTINGS, json=update_payload(password=SECRET, bind_password=BIND_SECRET)
        ),
    ),
    "save-keep-bind-password": (
        200,
        lambda api: api.put(SETTINGS, json=update_payload(password=SECRET)),
    ),
    "save-wrong-password": (
        422,
        lambda api: api.put(
            SETTINGS, json=update_payload(password="x" + SECRET, bind_password=BIND_SECRET)
        ),
    ),
    "save-too-long-password": (
        422,
        lambda api: api.put(SETTINGS, json=update_payload(password=LONG_PASSWORD)),
    ),
    "save-too-long-bind-password": (
        422,
        lambda api: api.put(
            SETTINGS, json=update_payload(password=SECRET, bind_password=LONG_PASSWORD)
        ),
    ),
    "save-endpoint-change-without-bind-password": (
        422,
        lambda api: api.put(SETTINGS, json=update_payload(password=SECRET, host="dc2.corp.test")),
    ),
    "save-stale-revision": (
        409,
        lambda api: api.put(
            SETTINGS, json=update_payload(9, password=SECRET, bind_password=BIND_SECRET)
        ),
    ),
    "test-ok": (
        200,
        lambda api: api.post(
            SETTINGS_TEST, json=probe_payload(password=SECRET, bind_password=BIND_SECRET)
        ),
    ),
    "test-wrong-password": (
        200,
        lambda api: api.post(
            SETTINGS_TEST, json=probe_payload(password="x" + SECRET, bind_password=BIND_SECRET)
        ),
    ),
    "test-too-long-password": (
        422,
        lambda api: api.post(SETTINGS_TEST, json=probe_payload(password=LONG_PASSWORD)),
    ),
    "read": (200, lambda api: api.get(SETTINGS)),
}


async def _stored_token(api: Api) -> str:
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text("select bind_password_encrypted from directory_settings")
            )
            return str(rows.scalar_one())
    finally:
        await engine.dispose()


@pytest.mark.parametrize("case", list(REQUESTS))
async def test_settings_responses_and_errors_never_echo_any_password(
    api: Api, caplog: pytest.LogCaptureFixture, case: str
) -> None:
    """Scenario: 저장·연결 테스트·조회의 성공·오류 응답과 로그에 입력한 비밀번호와 암호문이 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_admin_directory_password(api, SECRET)
    token = await _stored_token(api)
    caplog.set_level(logging.DEBUG)
    expected_status, send = REQUESTS[case]
    # When
    response = await send(api)
    # Then
    then_status_is(response, expected_status)
    searched = [response.text, "".join(response.headers.values()), caplog.text]
    for secret in (SECRET, BIND_SECRET, BIND_PASSWORD, LONG_PASSWORD, token):
        for place in searched:
            assert secret not in place
    body = response.json()
    assert not any("password" in key.lower() for key in body)
    assert all("input" not in err for err in body.get("errors") or [])
    assert (await _stored_token(api)) not in searched[0]


async def test_stored_bind_password_is_encrypted_with_configured_key(api: Api) -> None:
    """Scenario: DB에는 평문이 아니라 설정된 키로 풀리는 암호문이 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    token = await _stored_token(api)
    # Then
    assert token != BIND_PASSWORD
    assert BIND_PASSWORD not in token
    assert Fernet(TEST_FERNET_KEY.encode()).decrypt(token.encode()).decode() == BIND_PASSWORD


async def test_a_new_bind_password_replaces_the_stored_ciphertext(api: Api) -> None:
    """Scenario: 새 바인드 비밀번호로 저장하면 암호문이 새 값으로 바뀐다(평문은 여전히 없다)."""
    # Given
    await given_logged_in_as(api, role="admin")
    before = await _stored_token(api)
    # When
    saved = await api.put(
        SETTINGS, json=update_payload(host="dc2.corp.test", bind_password=BIND_SECRET)
    )
    # Then
    then_status_is(saved, 200)
    after = await _stored_token(api)
    assert after != before
    assert Fernet(TEST_FERNET_KEY.encode()).decrypt(after.encode()).decode() == BIND_SECRET
    assert BIND_SECRET not in after


async def test_saving_without_a_bind_password_keeps_the_stored_password(api: Api) -> None:
    """Scenario: 비밀번호를 비우고 저장하면 저장된 비밀번호가 그대로 풀린다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    saved = await api.put(SETTINGS, json=update_payload(connect_timeout_seconds=9))
    # Then
    then_status_is(saved, 200)
    token = await _stored_token(api)
    assert Fernet(TEST_FERNET_KEY.encode()).decrypt(token.encode()).decode() == BIND_PASSWORD


async def test_settings_changes_leave_no_password_in_any_table(api: Api) -> None:
    """Scenario: 설정 저장·연결 테스트(성공·실패)를 해도 어떤 테이블에도 평문 비밀번호가 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    given_admin_directory_password(api, SECRET)
    wrong = SECRET + "-wrong"
    # When
    await when_admin_saves_and_tests_with_wrong_and_right_passwords(
        api, right=SECRET, wrong=wrong, bind_password=BIND_SECRET, host="dc2.corp.test"
    )
    # Then
    await then_no_table_holds_the_passwords(
        api,
        TABLES,
        passwords=[SECRET, wrong, BIND_SECRET, BIND_PASSWORD],
        saved_host="dc2.corp.test",
    )
