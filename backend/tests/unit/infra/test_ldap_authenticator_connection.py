"""ldap3 어댑터: 연결·TLS·정리 실패 분류. 보안 연결 방식 none/ssl/starttls를 모두 본다."""

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
    """소켓·타임아웃 오류는 연결 단계의 사용 불가로 분류한다."""
    # given: 해당 호출에서 오류를 내는 디렉터리
    directory.faults[method] = fault

    # when: 로그인을 시도한다
    error = await failure(directory)

    # then: 연결 단계의 DirectoryUnavailableError다
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
    """SSL 오류는 TLS 단계의 사용 불가로 분류한다."""
    # given: open에서 SSL 오류를 내는 디렉터리
    directory.faults["open"] = fault

    # when: 로그인을 시도한다
    error = await failure(directory)

    # then: TLS 단계의 DirectoryUnavailableError다
    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.TLS


async def test_starttls_failure_is_unavailable_at_tls(directory: MockDirectory) -> None:
    """STARTTLS 실패는 TLS 단계의 사용 불가이며 bind까지 가지 않는다."""
    # given: start_tls에서 실패하는 디렉터리
    directory.faults["start_tls"] = LDAPStartTLSError("refused")

    # when: STARTTLS로 로그인을 시도한다
    error = await failure(directory, security=SecurityMode.STARTTLS, port=389)

    # then: TLS 단계 오류이고 bind를 호출하지 않았다
    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls  # TLS가 안 되면 비밀번호를 보내는 bind까지 가지 않는다


async def test_mock_server_that_refuses_starttls_reports_tls_stage(
    directory: MockDirectory,
) -> None:
    """STARTTLS를 거부하는 서버는 TLS 단계로 보고한다."""
    # when: STARTTLS로 로그인을 시도한다 (전제: STARTTLS를 지원하지 않는 모의 서버)
    error = await failure(directory, security=SecurityMode.STARTTLS, port=389)

    # then: TLS 단계 오류이고 bind를 호출하지 않았다
    assert isinstance(error, DirectoryUnavailableError)
    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls


async def test_starttls_calls_start_tls_before_binding(directory: MockDirectory) -> None:
    """STARTTLS는 bind 전에 start_tls를 호출한다."""
    # given: start_tls에서 실패하는 디렉터리
    directory.faults["start_tls"] = LDAPStartTLSError("refused")

    # when: STARTTLS로 로그인을 시도한다
    await failure(directory, security=SecurityMode.STARTTLS, port=389)

    # then: 호출 순서가 open, start_tls로 시작한다
    assert directory.calls[:2] == ["open", "start_tls"]


@pytest.mark.parametrize(("security", "port"), [(SecurityMode.SSL, 636), (SecurityMode.NONE, 389)])
async def test_ssl_and_none_do_not_call_start_tls(
    directory: MockDirectory, security: SecurityMode, port: int
) -> None:
    """SSL과 평문 연결은 start_tls를 호출하지 않는다."""
    # when: SSL 또는 평문으로 로그인한다
    await login(directory, security=security, port=port)

    # then: start_tls 호출이 없다
    assert "start_tls" not in directory.calls


async def test_plain_connection_logs_in_without_any_tls_step(directory: MockDirectory) -> None:
    """평문 연결은 TLS 단계 없이 로그인된다."""
    # when: 평문 연결로 로그인한다
    user = await login(directory, security=SecurityMode.NONE, port=389)

    # then: 로그인 아이디가 맞고 start_tls 호출이 없다
    assert user.login_id == "kim"
    assert "start_tls" not in directory.calls


@pytest.mark.parametrize("fault_method", ["bind", "search"])
async def test_connection_is_unbound_even_when_the_flow_fails(
    directory: MockDirectory, fault_method: str
) -> None:
    """흐름이 실패해도 연결은 unbind로 정리한다."""
    # given: bind 또는 search에서 소켓 오류를 내는 디렉터리
    directory.faults[fault_method] = LDAPSocketReceiveError("reset")

    # when: 로그인을 시도한다
    await failure(directory)

    # then: 마지막 호출이 unbind다
    assert directory.calls[-1] == "unbind"


async def test_connection_is_unbound_after_success_and_after_bad_password(
    directory: MockDirectory,
) -> None:
    """성공 뒤와 비밀번호 오류 뒤에도 연결을 unbind로 정리한다."""
    # when: 로그인에 성공한다
    await login(directory)
    # then: 마지막 호출이 unbind다
    assert directory.calls[-1] == "unbind"

    # when: 틀린 비밀번호로 로그인한다
    await failure(directory, attempt="Wrong-password-1")
    # then: 마지막 호출이 unbind다
    assert directory.calls[-1] == "unbind"


async def test_every_connection_is_unbound_when_the_user_is_not_found(
    directory: MockDirectory,
) -> None:
    """사용자를 찾지 못해도 모든 연결을 unbind한다."""
    # when: 없는 아이디로 로그인한다
    await failure(directory, login_id="nobody")

    # then: 연결 1개에 unbind 1번이다
    assert directory.calls.count("unbind") == len(directory.connections) == 1


async def test_settings_are_read_per_call(directory: MockDirectory) -> None:
    """설정은 호출마다 읽는다."""
    # given: 어댑터와 서로 다른 두 설정
    adapter = make_adapter(directory)
    first = make_directory_settings()
    second = make_directory_settings(connect_timeout_seconds=9)

    # when: 첫 설정으로 인증한다
    await adapter.authenticate(first, "dc=corp,dc=test", LoginId("kim"), Password(PASSWORD))
    # when: 두 번째 설정으로 인증한다
    await adapter.authenticate(second, "dc=corp,dc=test", LoginId("kim"), Password(PASSWORD))

    # then: 연결 생성에 각 호출의 설정이 쓰였다
    assert [call[0] for call in directory.factory_calls] == [first, first, second, second]


def test_error_hierarchy_distinguishes_credentials_from_availability() -> None:
    """오류 계층은 자격 증명 오류와 사용 불가 오류를 구분한다."""
    # when·then: 클래스 상속 관계와 stage 기본값을 확인한다
    assert issubclass(InvalidCredentialsError, DirectoryError)
    assert issubclass(DirectoryUnavailableError, DirectoryError)
    assert issubclass(DirectoryMisconfiguredError, DirectoryUnavailableError)
    assert not issubclass(InvalidCredentialsError, DirectoryUnavailableError)
    assert DirectoryError(stage=VerificationStage.TLS).stage is VerificationStage.TLS
    assert DirectoryError().stage is None


def test_verification_stages_cover_the_new_service_account_steps() -> None:
    """검증 단계는 서비스 계정 흐름의 단계를 모두 포함한다."""
    # when·then: 단계 값 집합이 정해진 여섯 개와 같다
    assert {stage.value for stage in VerificationStage} == {
        "connect",
        "tls",
        "service_bind",
        "base_dn",
        "search",
        "bind",
    }
