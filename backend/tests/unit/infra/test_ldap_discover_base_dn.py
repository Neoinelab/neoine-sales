"""ldap3 어댑터: 서비스 계정 바인드 뒤 RootDSE에서 Base DN을 찾는다 (AC5).

RootDSE 읽기는 `MockDirectory.root_dse`로 모의한다(MOCK_SYNC가 빈 DN 항목을 지원하지 않는다).
실제 AD의 RootDSE 응답은 dev 서버에서 사람이 한 번 확인해야 한다(문서의 '미검증 영역').
"""

import ssl
import threading

import pytest
from ldap3.core.exceptions import LDAPSocketOpenError, LDAPStartTLSError

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.directory.settings import SecurityMode
from tests.factories_auth import BASE_DN, BIND_ACCOUNT, BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.ldap_adapter import discover, discovery_failure, make_adapter
from tests.support.ldap_mock import MockDirectory


async def test_discover_reads_default_naming_context_after_service_bind(
    directory: MockDirectory,
) -> None:
    found = await discover(directory)

    assert found == BASE_DN
    ((_, bind_user, secret),) = directory.factory_calls
    assert (bind_user, secret) == (BIND_ACCOUNT, BIND_PASSWORD)
    assert directory.calls.index("bind") < directory.calls.index("search")
    (search,) = directory.connections[0].search_args
    assert search["search_base"] == ""
    assert search["search_filter"] == "(objectClass=*)"
    assert "BASE" in str(search["search_scope"]).upper()
    assert "defaultNamingContext" in search["attributes"]  # type: ignore[operator]
    assert directory.calls[-1] == "unbind"


@pytest.mark.parametrize(
    "value",
    ["  dc=corp,dc=test  ", ["dc=corp,dc=test"], ["  dc=corp,dc=test ", "dc=other"]],
    ids=["padded-text", "list", "first-of-several"],
)
async def test_the_first_value_is_stripped_and_returned(
    directory: MockDirectory, value: str | list[str]
) -> None:
    directory.root_dse = {"defaultNamingContext": value}

    assert await discover(directory) == BASE_DN


@pytest.mark.parametrize(
    "root_dse",
    [
        {},
        {"defaultNamingContext": ""},
        {"defaultNamingContext": []},
        {"defaultNamingContext": "   "},
        {"defaultNamingContext": "dc=" + "x" * 510},
        {"defaultNamingContext": "dc=a\x00b"},
    ],
    ids=["missing", "empty", "empty-list", "blank", "too-long", "control-char"],
)
async def test_missing_or_blank_default_naming_context_is_base_dn_stage(
    directory: MockDirectory, root_dse: dict[str, str | list[str]]
) -> None:
    directory.root_dse = root_dse

    error = await discovery_failure(directory)

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.BASE_DN


async def test_a_rejected_root_dse_read_is_reported_at_the_base_dn_stage(
    directory: MockDirectory,
) -> None:
    directory.root_dse = None

    error = await discovery_failure(directory)

    assert isinstance(error, DirectoryUnavailableError)
    assert error.stage is VerificationStage.BASE_DN
    assert directory.calls[-1] == "unbind"


async def test_wrong_service_password_is_misconfigured_service_bind(
    directory: MockDirectory,
) -> None:
    error = await discovery_failure(directory, bind_password="Not-the-service-pw")  # noqa: S106

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND
    assert "search" not in directory.calls


@pytest.mark.parametrize("code", [49, 50, 53])
async def test_service_account_rejection_codes_are_misconfigured_service_bind(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_code = code

    error = await discovery_failure(directory)

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND


@pytest.mark.parametrize("code", [51, 52])
async def test_other_service_bind_failures_are_unavailable(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_code = code

    error = await discovery_failure(directory)

    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.SERVICE_BIND


@pytest.mark.parametrize(
    ("fault", "stage"),
    [
        (LDAPSocketOpenError("refused"), VerificationStage.CONNECT),
        (TimeoutError("t"), VerificationStage.CONNECT),
        (ssl.SSLError("handshake"), VerificationStage.TLS),
    ],
    ids=["socket", "timeout", "ssl"],
)
async def test_connection_failures_report_their_stage(
    directory: MockDirectory, fault: BaseException, stage: VerificationStage
) -> None:
    directory.faults["open"] = fault

    error = await discovery_failure(directory)

    assert type(error) is DirectoryUnavailableError
    assert error.stage is stage
    assert "bind" not in directory.calls


async def test_starttls_failure_stops_before_the_service_account_bind(
    directory: MockDirectory,
) -> None:
    directory.faults["start_tls"] = LDAPStartTLSError("refused")

    error = await discovery_failure(directory, security=SecurityMode.STARTTLS, port=389)

    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls  # 서비스 계정 비밀번호를 평문으로 보내지 않는다


@pytest.mark.parametrize(
    ("security", "port"),
    [(SecurityMode.SSL, 636), (SecurityMode.NONE, 389)],
)
async def test_ssl_and_none_discover_without_start_tls(
    directory: MockDirectory, security: SecurityMode, port: int
) -> None:
    assert await discover(directory, security=security, port=port) == BASE_DN
    assert "start_tls" not in directory.calls


async def test_discover_runs_off_the_event_loop() -> None:
    mock = MockDirectory()

    await make_adapter(mock).discover_base_dn(make_directory_settings())

    loop_thread = threading.get_ident()
    assert mock.factory_threads
    assert all(thread != loop_thread for thread in mock.factory_threads)
    assert all(thread != loop_thread for _, thread in mock.log)
