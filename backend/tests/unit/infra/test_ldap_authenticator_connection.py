"""ldap3 어댑터: 연결·TLS·정리 실패 분류 (AC8). 보안 연결 방식 none/ssl/starttls를 모두 본다."""

import ssl
from typing import TYPE_CHECKING

import pytest
from ldap3.core.exceptions import (
    LDAPResponseTimeoutError,
    LDAPSocketOpenError,
    LDAPSocketReceiveError,
    LDAPStartTLSError,
)

from app.application.ports.directory import (
    DirectoryError,
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from app.domain.directory.settings import SecurityMode
from tests.factories_directory import make_directory_settings
from tests.support.ldap_adapter import PASSWORD, failure, login, make_adapter

if TYPE_CHECKING:
    from tests.support.ldap_mock import MockDirectory


@pytest.mark.parametrize(
    "fault",
    [
        LDAPSocketOpenError("refused"),
        LDAPSocketReceiveError("reset"),
        LDAPResponseTimeoutError("timed out"),
        TimeoutError("socket timed out"),
        ConnectionRefusedError("refused"),
    ],
    ids=lambda f: type(f).__name__,
)
@pytest.mark.parametrize("method", ["open", "bind", "search"])
async def test_socket_and_timeout_errors_are_unavailable_at_connect(
    directory: MockDirectory, method: str, fault: BaseException
) -> None:
    directory.faults[method] = fault

    error = await failure(directory)

    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.CONNECT


@pytest.mark.parametrize(
    "fault",
    [ssl.SSLError("handshake failure"), ssl.SSLCertVerificationError("bad cert")],
    ids=lambda f: type(f).__name__,
)
async def test_ssl_errors_are_unavailable_at_tls(
    directory: MockDirectory, fault: BaseException
) -> None:
    directory.faults["open"] = fault

    error = await failure(directory)

    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.TLS


async def test_starttls_failure_is_unavailable_at_tls(directory: MockDirectory) -> None:
    directory.faults["start_tls"] = LDAPStartTLSError("refused")

    error = await failure(directory, security=SecurityMode.STARTTLS, port=389)

    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls  # TLS가 안 되면 비밀번호를 보내는 bind까지 가지 않는다


async def test_mock_server_that_refuses_starttls_reports_tls_stage(
    directory: MockDirectory,
) -> None:
    error = await failure(directory, security=SecurityMode.STARTTLS, port=389)

    assert isinstance(error, DirectoryUnavailableError)
    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls


async def test_starttls_calls_start_tls_before_binding(directory: MockDirectory) -> None:
    directory.faults["start_tls"] = LDAPStartTLSError("refused")

    await failure(directory, security=SecurityMode.STARTTLS, port=389)

    assert directory.calls[:2] == ["open", "start_tls"]


@pytest.mark.parametrize(("security", "port"), [(SecurityMode.SSL, 636), (SecurityMode.NONE, 389)])
async def test_ssl_and_none_do_not_call_start_tls(
    directory: MockDirectory, security: SecurityMode, port: int
) -> None:
    await login(directory, security=security, port=port)

    assert "start_tls" not in directory.calls


async def test_plain_connection_logs_in_without_any_tls_step(directory: MockDirectory) -> None:
    user = await login(directory, security=SecurityMode.NONE, port=389)

    assert user.login_id == "kim"
    assert "start_tls" not in directory.calls


@pytest.mark.parametrize("fault_method", ["bind", "search"])
async def test_connection_is_unbound_even_when_the_flow_fails(
    directory: MockDirectory, fault_method: str
) -> None:
    directory.faults[fault_method] = LDAPSocketReceiveError("reset")

    await failure(directory)

    assert directory.calls[-1] == "unbind"


async def test_connection_is_unbound_after_success_and_after_bad_password(
    directory: MockDirectory,
) -> None:
    await login(directory)
    assert directory.calls[-1] == "unbind"

    await failure(directory, attempt="Wrong-password-1")
    assert directory.calls[-1] == "unbind"


async def test_every_connection_is_unbound_when_the_user_is_not_found(
    directory: MockDirectory,
) -> None:
    await failure(directory, login_id="nobody")

    assert directory.calls.count("unbind") == len(directory.connections) == 1


async def test_settings_are_read_per_call(directory: MockDirectory) -> None:
    adapter = make_adapter(directory)
    first = make_directory_settings()
    second = make_directory_settings(connect_timeout_seconds=9)

    await adapter.authenticate(first, "dc=corp,dc=test", LoginId("kim"), Password(PASSWORD))
    await adapter.authenticate(second, "dc=corp,dc=test", LoginId("kim"), Password(PASSWORD))

    assert [call[0] for call in directory.factory_calls] == [first, first, second, second]


def test_error_hierarchy_distinguishes_credentials_from_availability() -> None:
    assert issubclass(InvalidCredentialsError, DirectoryError)
    assert issubclass(DirectoryUnavailableError, DirectoryError)
    assert issubclass(DirectoryMisconfiguredError, DirectoryUnavailableError)
    assert not issubclass(InvalidCredentialsError, DirectoryUnavailableError)
    assert DirectoryError(stage=VerificationStage.TLS).stage is VerificationStage.TLS
    assert DirectoryError().stage is None


def test_verification_stages_cover_the_new_service_account_steps() -> None:
    assert {stage.value for stage in VerificationStage} == {
        "connect",
        "tls",
        "service_bind",
        "base_dn",
        "search",
        "bind",
    }
