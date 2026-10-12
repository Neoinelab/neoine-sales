"""ldap3 어댑터: 연결·TLS·정리·probe 실패 분류 (T-A6~A10, A13~A15)."""

import ssl

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
from app.domain.directory.settings import DirectoryUrl
from tests.factories_auth import make_directory_settings
from tests.support.ldap_adapter import PASSWORD, failure, login, make_adapter
from tests.support.ldap_mock import MockDirectory, user_attributes


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

    error = await failure(
        directory,
        server_urls=(DirectoryUrl.parse("ldap://dc1.corp.test"),),
        use_starttls=True,
    )

    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls  # TLS가 안 되면 비밀번호를 보내는 bind까지 가지 않는다


async def test_mock_server_that_refuses_starttls_reports_tls_stage(
    directory: MockDirectory,
) -> None:
    error = await failure(
        directory,
        server_urls=(DirectoryUrl.parse("ldap://dc1.corp.test"),),
        use_starttls=True,
    )

    assert isinstance(error, DirectoryUnavailableError)
    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls


async def test_ldaps_connection_does_not_call_starttls(directory: MockDirectory) -> None:
    await login(directory)

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


async def test_settings_are_read_per_call(directory: MockDirectory) -> None:
    directory.add_entry(
        "cn=lee,ou=users,dc=corp,dc=test",
        user_attributes("lee", PASSWORD, displayName="표시", description="설명"),
    )
    adapter = make_adapter(directory)
    first = make_directory_settings()
    second = make_directory_settings(display_name_attribute="description")

    one = await adapter.authenticate(first, LoginId("lee"), Password(PASSWORD))
    two = await adapter.authenticate(second, LoginId("lee"), Password(PASSWORD))

    assert (one.display_name, two.display_name) == ("표시", "설명")
    assert [call[0] for call in directory.factory_calls] == [first, second]


async def test_probe_opens_without_binding(directory: MockDirectory) -> None:
    await make_adapter(directory).probe(make_directory_settings())

    assert "open" in directory.calls
    assert "bind" not in directory.calls
    assert "search" not in directory.calls
    assert directory.calls[-1] == "unbind"
    assert directory.factory_calls[0][2] is None  # 비밀번호 없이 연결을 만든다


@pytest.mark.parametrize(
    ("fault", "stage"),
    [
        (LDAPSocketOpenError("refused"), VerificationStage.CONNECT),
        (TimeoutError("t"), VerificationStage.CONNECT),
        (ssl.SSLError("handshake"), VerificationStage.TLS),
    ],
    ids=["socket", "timeout", "ssl"],
)
async def test_probe_failure_reports_stage(
    directory: MockDirectory, fault: BaseException, stage: VerificationStage
) -> None:
    directory.faults["open"] = fault

    with pytest.raises(DirectoryUnavailableError) as caught:
        await make_adapter(directory).probe(make_directory_settings())

    assert caught.value.stage is stage


async def test_probe_with_starttls_failure_reports_tls(directory: MockDirectory) -> None:
    settings = make_directory_settings(
        server_urls=(DirectoryUrl.parse("ldap://dc1.corp.test"),), use_starttls=True
    )

    with pytest.raises(DirectoryUnavailableError) as caught:
        await make_adapter(directory).probe(settings)

    assert caught.value.stage is VerificationStage.TLS
    assert "bind" not in directory.calls


def test_error_hierarchy_distinguishes_credentials_from_availability() -> None:
    assert issubclass(InvalidCredentialsError, DirectoryError)
    assert issubclass(DirectoryUnavailableError, DirectoryError)
    assert issubclass(DirectoryMisconfiguredError, DirectoryUnavailableError)
    assert not issubclass(InvalidCredentialsError, DirectoryUnavailableError)
    assert DirectoryError(stage=VerificationStage.TLS).stage is VerificationStage.TLS
    assert DirectoryError().stage is None
