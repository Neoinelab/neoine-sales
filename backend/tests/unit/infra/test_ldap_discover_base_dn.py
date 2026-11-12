"""ldap3 어댑터: 서비스 계정 바인드 뒤 RootDSE에서 Base DN을 찾는다 .

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
    """서비스 계정으로 바인드한 뒤 RootDSE의 defaultNamingContext를 읽는다."""
    # when: Base DN을 탐색한다 (전제: 모의 디렉터리)
    found = await discover(directory)

    # then: Base DN을 돌려주고 서비스 계정 바인드 뒤 RootDSE를 조회한 뒤 연결을 닫는다
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
    """첫 값을 공백 제거해 돌려준다."""
    # given: 공백이 있거나 여러 값인 defaultNamingContext
    directory.root_dse = {"defaultNamingContext": value}

    # when: 탐색한다
    result = await discover(directory)
    # then: 정리된 첫 값이 Base DN이다
    assert result == BASE_DN


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
    """defaultNamingContext가 없거나 비었거나 비정상이면 Base DN 단계의 설정 오류다."""
    # given: 비정상 RootDSE
    directory.root_dse = root_dse

    # when: 탐색 실패를 받는다 (비었거나 공백인 naming context)
    error = await discovery_failure(directory)

    # then: BASE_DN 단계의 DirectoryMisconfiguredError다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.BASE_DN


async def test_a_rejected_root_dse_read_is_reported_at_the_base_dn_stage(
    directory: MockDirectory,
) -> None:
    """RootDSE 읽기가 거절되면 Base DN 단계의 연결 불가 오류이고 연결을 닫는다."""
    # given: RootDSE 읽기가 거절되는 디렉터리
    directory.root_dse = None

    # when: 탐색 실패를 받는다 (RootDSE 읽기 거절)
    error = await discovery_failure(directory)

    # then: BASE_DN 단계의 DirectoryUnavailableError이고 연결을 닫았다
    assert isinstance(error, DirectoryUnavailableError)
    assert error.stage is VerificationStage.BASE_DN
    assert directory.calls[-1] == "unbind"


async def test_wrong_service_password_is_misconfigured_service_bind(
    directory: MockDirectory,
) -> None:
    """서비스 계정 비밀번호가 틀리면 SERVICE_BIND 단계의 설정 오류이고 검색하지 않는다."""
    # when: 틀린 서비스 비밀번호로 탐색 실패를 받는다 (전제: 모의 디렉터리)
    error = await discovery_failure(directory, bind_password="Not-the-service-pw")  # noqa: S106

    # then: SERVICE_BIND 단계의 DirectoryMisconfiguredError이고 검색은 하지 않았다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND
    assert "search" not in directory.calls


@pytest.mark.parametrize("code", [49, 50, 53])
async def test_service_account_rejection_codes_are_misconfigured_service_bind(
    directory: MockDirectory, code: int
) -> None:
    """서비스 계정 거절 코드(49·50·53)는 SERVICE_BIND 단계의 설정 오류다."""
    # given: 바인드가 해당 코드로 거절되는 디렉터리
    directory.bind_code = code

    # when: 탐색 실패를 받는다 (서비스 계정 거절 코드)
    error = await discovery_failure(directory)

    # then: SERVICE_BIND 단계의 DirectoryMisconfiguredError다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND


@pytest.mark.parametrize("code", [51, 52])
async def test_other_service_bind_failures_are_unavailable(
    directory: MockDirectory, code: int
) -> None:
    """그 밖의 서비스 바인드 실패 코드(51·52)는 연결 불가 오류다."""
    # given: 바인드가 해당 코드로 실패하는 디렉터리
    directory.bind_code = code

    # when: 탐색 실패를 받는다 (그 밖의 바인드 실패)
    error = await discovery_failure(directory)

    # then: SERVICE_BIND 단계의 DirectoryUnavailableError다
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
    """연결 실패는 원인에 맞는 단계로 보고하고 바인드하지 않는다."""
    # given: 연결 단계 결함
    directory.faults["open"] = fault

    # when: 탐색 실패를 받는다 (연결 실패)
    error = await discovery_failure(directory)

    # then: 해당 단계의 DirectoryUnavailableError이고 바인드는 하지 않았다
    assert type(error) is DirectoryUnavailableError
    assert error.stage is stage
    assert "bind" not in directory.calls


async def test_starttls_failure_stops_before_the_service_account_bind(
    directory: MockDirectory,
) -> None:
    """STARTTLS 실패는 서비스 계정 바인드 전에 멈춘다."""
    # given: STARTTLS 협상이 실패하는 디렉터리
    directory.faults["start_tls"] = LDAPStartTLSError("refused")

    # when: STARTTLS 설정으로 탐색 실패를 받는다
    error = await discovery_failure(directory, security=SecurityMode.STARTTLS, port=389)

    # then: TLS 단계 오류이고 비밀번호를 평문으로 보내는 바인드는 하지 않았다
    assert error.stage is VerificationStage.TLS
    assert "bind" not in directory.calls  # 서비스 계정 비밀번호를 평문으로 보내지 않는다


@pytest.mark.parametrize(
    ("security", "port"),
    [(SecurityMode.SSL, 636), (SecurityMode.NONE, 389)],
)
async def test_ssl_and_none_discover_without_start_tls(
    directory: MockDirectory, security: SecurityMode, port: int
) -> None:
    """SSL·평문 연결은 STARTTLS 없이 탐색한다."""
    # when: 탐색한다
    result = await discover(directory, security=security, port=port)
    # then: Base DN을 얻고 STARTTLS는 호출하지 않는다 (전제: 모의 디렉터리)
    assert result == BASE_DN
    assert "start_tls" not in directory.calls


async def test_discover_runs_off_the_event_loop() -> None:
    """탐색은 이벤트 루프 밖 스레드에서 실행된다."""
    # given: 모의 디렉터리와 어댑터
    mock = MockDirectory()

    # when: Base DN을 탐색한다
    await make_adapter(mock).discover_base_dn(make_directory_settings())

    # then: 연결 생성과 호출이 이벤트 루프 스레드가 아닌 곳에서 일어났다
    loop_thread = threading.get_ident()
    assert mock.factory_threads
    assert all(thread != loop_thread for thread in mock.factory_threads)
    assert all(thread != loop_thread for _, thread in mock.log)
