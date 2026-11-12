"""서비스·사용자 비밀번호가 오류·로그에 남지 않고, 이벤트 루프를 막지 않는다."""

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

import pytest
from ldap3.core.exceptions import LDAPSocketOpenError

from app.application.ports.directory import DirectoryError
from app.domain.auth.credentials import LoginId, Password
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.factories_auth import BASE_DN, BIND_ACCOUNT, BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.ldap_mock import MockDirectory

if TYPE_CHECKING:
    from collections.abc import Callable

SECRET = "Zq9-never-leak-this-4242"  # noqa: S105 - 테스트용 더미 값(사용자 비밀번호)
WRONG = "Wr0ng-attempt-9191"


def _directory() -> MockDirectory:
    mock = MockDirectory()
    mock.add_user("kim", SECRET, display_name="김영업", mail="kim@corp.test")
    return mock


def _chain(error: BaseException | None) -> list[BaseException]:
    seen: list[BaseException] = []
    while error is not None and error not in seen:
        seen.append(error)
        error = error.__cause__ or error.__context__
    return seen


def _wrong_password(mock: MockDirectory) -> None:
    del mock


def _socket_down(mock: MockDirectory) -> None:
    mock.faults["open"] = LDAPSocketOpenError("cannot reach server")


def _service_rejected(mock: MockDirectory) -> None:
    mock.bind_codes_by_user[BIND_ACCOUNT] = 53


def _user_rejected(mock: MockDirectory) -> None:
    mock.bind_codes_by_user["cn=kim,ou=users,dc=corp,dc=test"] = 53


def _search_fails(mock: MockDirectory) -> None:
    mock.faults["search"] = LDAPSocketOpenError("reset during search")


ARRANGEMENTS = [
    _wrong_password,
    _socket_down,
    _service_rejected,
    _user_rejected,
    _search_fails,
]


@pytest.mark.parametrize("arrange", ARRANGEMENTS)
async def test_errors_and_logs_never_contain_either_password(
    caplog: pytest.LogCaptureFixture, arrange: Callable[[MockDirectory], None]
) -> None:
    """실패 원인과 관계없이 오류·로그에 서비스·사용자 비밀번호가 남지 않는다."""
    # given: 사용자가 있고 실패 상황이 준비된 디렉터리
    mock = _directory()
    arrange(mock)
    attempt = WRONG if arrange is _wrong_password else SECRET
    caplog.set_level(logging.DEBUG)
    logging.getLogger("ldap3").setLevel(logging.DEBUG)

    # when·then: 인증하면 DirectoryError가 난다
    with pytest.raises(DirectoryError) as caught:
        await LdapDirectoryAuthenticator(mock.factory).authenticate(
            make_directory_settings(), BASE_DN, LoginId("kim"), Password(attempt)
        )

    # then: 오류 체인과 로그 어디에도 비밀번호가 없다
    for error in _chain(caught.value):
        text = f"{error!s}|{error!r}|{error.args!r}"
        for secret in (SECRET, WRONG, BIND_PASSWORD):
            assert secret not in text
    for secret in (SECRET, WRONG, BIND_PASSWORD):
        assert secret not in caplog.text


@pytest.mark.parametrize("arrange", [_socket_down, _service_rejected])
async def test_discovery_errors_and_logs_never_contain_the_service_password(
    caplog: pytest.LogCaptureFixture, arrange: Callable[[MockDirectory], None]
) -> None:
    """Base DN 탐색 실패의 오류·로그에 서비스 비밀번호가 남지 않는다."""
    # given: 실패 상황이 준비된 디렉터리
    mock = _directory()
    arrange(mock)
    caplog.set_level(logging.DEBUG)

    # when·then: 탐색하면 DirectoryError가 난다
    with pytest.raises(DirectoryError) as caught:
        await LdapDirectoryAuthenticator(mock.factory).discover_base_dn(make_directory_settings())

    # then: 오류 체인과 로그에 서비스 비밀번호가 없다
    for error in _chain(caught.value):
        assert BIND_PASSWORD not in f"{error!s}|{error!r}|{error.args!r}"
    assert BIND_PASSWORD not in caplog.text


async def test_errors_never_contain_the_password_when_the_search_matches_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """검색 결과가 없어 실패해도 오류·로그에 비밀번호가 남지 않는다."""
    # given: 사용자가 있지만 검색 필터가 아무도 찾지 못하는 디렉터리
    mock = MockDirectory()
    mock.add_user("kim", SECRET)
    caplog.set_level(logging.DEBUG)

    # when·then: 인증하면 DirectoryError가 난다
    with pytest.raises(DirectoryError) as caught:
        await LdapDirectoryAuthenticator(mock.factory).authenticate(
            make_directory_settings(user_filter="(sAMAccountName=zz{login_id})"),
            BASE_DN,
            LoginId("kim"),
            Password(SECRET),
        )

    # then: 오류 체인과 로그에 비밀번호가 없다
    for error in _chain(caught.value):
        assert SECRET not in f"{error!s}|{error!r}|{error.args!r}"
    assert SECRET not in caplog.text
    assert BIND_PASSWORD not in caplog.text


async def test_calls_run_off_the_event_loop() -> None:
    """어댑터 호출이 이벤트 루프를 막지 않고 별도 스레드에서 실행된다."""
    # given: 응답이 0.2초 지연되는 디렉터리와 주기적으로 도는 ticker 코루틴
    mock = _directory()
    mock.delay = 0.2
    adapter = LdapDirectoryAuthenticator(mock.factory)
    loop_thread = threading.get_ident()
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    # when: 인증하는 동안 ticker를 함께 돌린다
    task = asyncio.create_task(ticker())
    try:
        await adapter.authenticate(
            make_directory_settings(), BASE_DN, LoginId("kim"), Password(SECRET)
        )
    finally:
        task.cancel()

    # then: 인증 중에도 ticker가 돌았고 연결 생성은 이벤트 루프 스레드가 아니었다
    assert ticks >= 4, "bind가 이벤트 루프를 막으면 그 동안 다른 코루틴이 돌지 못한다"
    assert mock.factory_threads
    assert all(thread != loop_thread for thread in mock.factory_threads)
    assert all(thread != loop_thread for _, thread in mock.log)
