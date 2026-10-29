"""ldap3 연결 생성·열기·정리 도우미. 서버는 호스트 하나·포트 하나이고 인증서는 검증하지 않는다.

SSL·StartTLS 모두 서버 인증서를 검증하지 않는다(ssl.CERT_NONE, 사용자 결정: 내부망 AD의 사설 CA).
도청은 막지만 중간자 공격은 막지 못하며, 이 사실은 화면 경고와 문서에 적는다.
"""

import contextlib
import ssl
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from ldap3 import SIMPLE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException

from app.application.ports.directory import DirectoryError, VerificationStage
from app.domain.directory.settings import RECEIVE_TIMEOUT_SECONDS, SecurityMode
from app.infra.auth.ldap_errors import failure_stage, service_bind_failure, unavailable

if TYPE_CHECKING:
    from app.domain.directory.settings import DirectorySettings

ConnectionFactory = Callable[["DirectorySettings", str | None, str | None], Connection]


def default_connection_factory(
    settings: DirectorySettings, bind_user: str | None, password: str | None
) -> Connection:
    """열지 않은 ldap3 연결을 만든다. 서비스 계정과 사용자 바인드가 같은 팩토리를 쓴다."""
    connection = settings.connection
    server = Server(
        connection.host,
        port=connection.port,
        use_ssl=connection.security is SecurityMode.SSL,
        tls=Tls(validate=ssl.CERT_NONE),
        connect_timeout=connection.connect_timeout_seconds,
        get_info="NO_INFO",
    )
    return Connection(
        server,
        user=bind_user,
        password=password,
        authentication=SIMPLE,
        raise_exceptions=False,
        receive_timeout=RECEIVE_TIMEOUT_SECONDS,
        read_only=True,
        auto_bind=False,
        auto_referrals=False,
    )


def guarded[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except DirectoryError:
        raise
    except (LDAPException, OSError) as error:
        raise unavailable(failure_stage(error)) from None


def unbind(connection: Connection) -> None:
    with contextlib.suppress(Exception):
        connection.unbind()


def open_secure(connection: Connection, settings: DirectorySettings) -> None:
    """연결을 열고(LDAPS는 TLS 포함) StartTLS면 협상까지 마친다. 비밀번호는 그 뒤에 보낸다."""

    def action() -> None:
        connection.open()
        if settings.connection.security is SecurityMode.STARTTLS and not connection.start_tls():
            raise unavailable(VerificationStage.TLS)

    guarded(action)


@contextlib.contextmanager
def service_session(
    connect: ConnectionFactory, settings: DirectorySettings
) -> Iterator[Connection]:
    """서비스 계정으로 바인드한 연결. 어떤 경우에도 닫는다."""
    connection = connect(
        settings, settings.connection.bind_account, settings.bind_password.reveal()
    )
    try:
        open_secure(connection, settings)
        if not guarded(connection.bind):
            raise service_bind_failure((connection.result or {}).get("result"))
        yield connection
    finally:
        unbind(connection)
