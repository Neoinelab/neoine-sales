"""DirectoryAuthenticator Port의 ldap3 구현(AD). 사용자 자기 자격증명으로 바인드한 뒤 속성을 읽는다.

ldap3은 동기 라이브러리이므로 호출마다 asyncio.to_thread에서 실행한다. 설정은 호출 때마다 받고
어댑터는 상태를 갖지 않는다. 타임아웃은 설정의 connect/receive 초를 ldap3에 넘겨 적용한다.
비밀번호는 연결 팩토리에만 전달하고 예외·로그에는 쓰지 않는다(ldap3 로깅도 켜지 않는다).
"""

import asyncio
import contextlib
import dataclasses
import logging
import ssl
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ldap3 import SIMPLE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn

from app.application.ports.directory import (
    DirectoryError,
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.directory.rules import PLACEHOLDER
from app.infra.auth.ldap_errors import MESSAGES, bind_failure, failure_stage, unavailable

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.directory.settings import DirectorySettings

logger = logging.getLogger(__name__)

ConnectionFactory = Callable[["DirectorySettings", str | None, str | None], Connection]
SEARCH_SIZE_LIMIT = 2  # 1건이 아니면 설정 오류이므로 2건까지만 받으면 판단할 수 있다
_INVALID_CREDENTIALS = "아이디 또는 비밀번호가 올바르지 않습니다"


def default_connection_factory(
    settings: DirectorySettings, bind_user: str | None, password: str | None
) -> Connection:
    """열지 않은 ldap3 연결을 첫 서버(servers[0])로 만든다. 인증서는 항상 검증한다(CERT_REQUIRED).

    여러 서버는 ServerPool 없이 어댑터가 URL별로 이 팩토리를 호출해 순회한다(ServerPool은 모든
    서버가 실패하면 영원히 기다린다).
    """
    tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_data=settings.ca_cert_pem)
    url = settings.server_urls[0]
    server = Server(
        url.host,
        port=url.port,
        use_ssl=url.scheme == "ldaps",
        tls=tls,
        connect_timeout=settings.connect_timeout_seconds,
        get_info="NO_INFO",
    )
    return Connection(
        server,
        user=bind_user,
        password=password,
        authentication=SIMPLE,
        raise_exceptions=False,
        receive_timeout=settings.receive_timeout_seconds,
        read_only=True,
        auto_bind=False,
    )


def _bind_user(settings: DirectorySettings, login_id: str) -> str:
    value = escape_rdn(login_id) if settings.bind_template_is_dn else login_id
    return settings.bind_template.replace(PLACEHOLDER, value)


def _first(attributes: dict[str, Any], name: str) -> str | None:
    for key, value in attributes.items():
        if key.lower() == name.lower():
            item = value[0] if isinstance(value, list | tuple) and value else value
            text = str(item).strip() if item not in (None, [], ()) else ""
            return text or None
    return None


def _open_secure(connection: Connection, settings: DirectorySettings) -> None:
    """연결을 열고(LDAPS는 TLS 포함) 필요하면 StartTLS까지 마친다. 실패는 단계별 오류로 올린다."""
    try:
        connection.open()
        if settings.use_starttls and not connection.start_tls():
            raise unavailable(VerificationStage.TLS)
    except DirectoryError:
        raise
    except (LDAPException, OSError) as error:
        raise unavailable(failure_stage(error)) from None


def _open_any(
    connect: ConnectionFactory,
    settings: DirectorySettings,
    bind_user: str | None,
    secret: str | None,
) -> Connection:
    """서버 URL을 차례로 시도해 처음 열린 연결을 돌려준다. 모두 실패하면 마지막 오류를 올린다."""
    urls = settings.server_urls
    for index, url in enumerate(urls):
        target = settings if len(urls) == 1 else dataclasses.replace(settings, server_urls=(url,))
        connection = connect(target, bind_user, secret)
        try:
            _open_secure(connection, target)
        except DirectoryUnavailableError:
            _unbind(connection)
            if index == len(urls) - 1:
                raise
        except BaseException:
            _unbind(connection)
            raise
        else:
            return connection
    raise unavailable(VerificationStage.CONNECT)  # server_urls는 비어 있을 수 없다(도달 불가)


def _guarded[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except DirectoryError:
        raise
    except (LDAPException, OSError) as error:
        raise unavailable(failure_stage(error)) from None


def _unbind(connection: Connection) -> None:
    with contextlib.suppress(Exception):
        connection.unbind()


def _search_user(
    connection: Connection, settings: DirectorySettings, login_id: str
) -> DirectoryUser:
    search_filter = settings.user_filter.replace(PLACEHOLDER, escape_filter_chars(login_id))
    names = [settings.display_name_attribute, settings.email_attribute]
    _guarded(
        lambda: connection.search(
            settings.base_dn,
            search_filter,
            search_scope=SUBTREE,
            attributes=names,
            size_limit=SEARCH_SIZE_LIMIT,
        ),
    )
    entries = [e for e in (connection.response or []) if e.get("type") == "searchResEntry"]
    if len(entries) != 1:
        raise DirectoryMisconfiguredError(
            MESSAGES[VerificationStage.SEARCH], stage=VerificationStage.SEARCH
        )
    attributes = entries[0].get("attributes") or {}
    return DirectoryUser(
        login_id=login_id,
        display_name=_first(attributes, settings.display_name_attribute) or login_id,
        email=_first(attributes, settings.email_attribute),
    )


class LdapDirectoryAuthenticator:
    def __init__(self, connect: ConnectionFactory | None = None) -> None:
        self._connect = connect or default_connection_factory

    async def authenticate(
        self, settings: DirectorySettings, login_id: LoginId, password: Password
    ) -> DirectoryUser:
        secret = password.reveal()
        if not secret:
            # 빈 비밀번호는 익명 바인드로 통과될 수 있으므로 연결하지 않고 거부한다.
            raise InvalidCredentialsError(_INVALID_CREDENTIALS, stage=VerificationStage.BIND)
        return await asyncio.to_thread(self._authenticate, settings, login_id.value, secret)

    async def probe(self, settings: DirectorySettings) -> None:
        await asyncio.to_thread(self._probe, settings)

    def _authenticate(
        self, settings: DirectorySettings, login_id: str, secret: str
    ) -> DirectoryUser:
        try:
            connection = _open_any(self._connect, settings, _bind_user(settings, login_id), secret)
        except DirectoryUnavailableError as error:
            logger.warning("디렉터리 인증 실패: stage=%s", error.stage)
            raise
        try:
            if not _guarded(connection.bind):
                result = connection.result or {}
                raise bind_failure(result.get("result"))
            return _search_user(connection, settings, login_id)
        except DirectoryUnavailableError as error:
            logger.warning("디렉터리 인증 실패: stage=%s", error.stage)
            raise
        finally:
            _unbind(connection)

    def _probe(self, settings: DirectorySettings) -> None:
        _unbind(_open_any(self._connect, settings, None, None))
