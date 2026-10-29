"""DirectoryAuthenticator Port의 ldap3 구현(AD). 서비스 계정 search-then-bind.

흐름: (연결 -> TLS) -> 서비스 계정 바인드 -> 사용자 검색(로그인 아이디는 필터 값으로만 쓰고 DN에는
넣지 않는다) -> 찾은 항목의 DN과 사용자 비밀번호로 새 연결 바인드. Base DN은 설정 저장 때
RootDSE(defaultNamingContext)에서 찾아 저장한 값을 쓴다.

ldap3은 동기 라이브러리이므로 호출마다 asyncio.to_thread에서 실행한다. 설정은 호출 때마다 받고
어댑터는 상태를 갖지 않는다. 비밀번호는 연결 팩토리에만 전달하고 예외·로그에는 쓰지 않는다
(ldap3 로깅도 켜지 않는다). 서버 인증서는 검증하지 않는다(ldap_connection 참고).
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ldap3 import BASE, SUBTREE, Connection
from ldap3.utils.conv import escape_filter_chars

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.common.errors import InvalidValueError
from app.domain.directory import rules
from app.domain.directory.settings import DISPLAY_NAME_ATTRIBUTE, EMAIL_ATTRIBUTE
from app.infra.auth.ldap_connection import (
    ConnectionFactory,
    default_connection_factory,
    guarded,
    open_secure,
    service_session,
    unbind,
)
from app.infra.auth.ldap_errors import MESSAGES, bind_failure, unavailable

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.auth.credentials import LoginId, Password
    from app.domain.directory.settings import DirectorySettings

__all__ = ["LdapDirectoryAuthenticator", "default_connection_factory"]

logger = logging.getLogger(__name__)

SEARCH_SIZE_LIMIT = 2  # 1건이 아니면 설정 오류이므로 2건까지만 받으면 판단할 수 있다
BASE_DN_MAX = 512
_INVALID_CREDENTIALS = "아이디 또는 비밀번호가 올바르지 않습니다"
_NAMING_CONTEXT = "defaultNamingContext"
_SUCCESS = 0
_SIZE_LIMIT_EXCEEDED = 4


def _first(attributes: dict[str, Any], name: str) -> str | None:
    for key, value in attributes.items():
        if key.lower() == name.lower():
            item = value[0] if isinstance(value, list | tuple) and value else value
            text = str(item).strip() if item not in (None, [], ()) else ""
            return text or None
    return None


def _entries(connection: Connection) -> list[dict[str, Any]]:
    return [e for e in (connection.response or []) if e.get("type") == "searchResEntry"]


def _result_code(connection: Connection) -> object:
    return (connection.result or {}).get("result")


def _misconfigured(stage: VerificationStage) -> DirectoryMisconfiguredError:
    return DirectoryMisconfiguredError(MESSAGES[stage], stage=stage)


def _read_base_dn(connection: Connection) -> str:
    guarded(
        lambda: connection.search(
            "", "(objectClass=*)", search_scope=BASE, attributes=[_NAMING_CONTEXT]
        )
    )
    if _result_code(connection) != _SUCCESS:  # RootDSE 읽기가 거부되었다
        raise unavailable(VerificationStage.BASE_DN)
    entries = _entries(connection)
    value = _first(entries[0].get("attributes") or {}, _NAMING_CONTEXT) if entries else None
    if value is None:
        raise _misconfigured(VerificationStage.BASE_DN)
    try:
        rules.check_text(value, "base_dn", max_length=BASE_DN_MAX)
    except InvalidValueError:
        raise _misconfigured(VerificationStage.BASE_DN) from None
    return value


def _find_user(
    connection: Connection, settings: DirectorySettings, base_dn: str, login_id: str
) -> tuple[str, DirectoryUser]:
    search_filter = settings.connection.user_filter.replace(
        rules.PLACEHOLDER, escape_filter_chars(login_id)
    )
    guarded(
        lambda: connection.search(
            base_dn,
            search_filter,
            search_scope=SUBTREE,
            attributes=[DISPLAY_NAME_ATTRIBUTE, EMAIL_ATTRIBUTE],
            size_limit=SEARCH_SIZE_LIMIT,
        ),
    )
    code = _result_code(connection)
    if code == _SIZE_LIMIT_EXCEEDED:  # 2건 이상과 같은 분류(필터가 한 명으로 좁혀지지 않는다)
        raise _misconfigured(VerificationStage.SEARCH)
    if code != _SUCCESS:  # Base DN이 없거나 검색 권한이 없다
        raise _misconfigured(VerificationStage.BASE_DN)
    entries = _entries(connection)
    if not entries:
        raise InvalidCredentialsError(_INVALID_CREDENTIALS, stage=VerificationStage.SEARCH)
    if len(entries) > 1:
        raise _misconfigured(VerificationStage.SEARCH)
    attributes = entries[0].get("attributes") or {}
    user = DirectoryUser(
        login_id=login_id,
        display_name=_first(attributes, DISPLAY_NAME_ATTRIBUTE) or login_id,
        email=_first(attributes, EMAIL_ATTRIBUTE),
    )
    return str(entries[0]["dn"]), user


def _logged[**P, T](action: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    try:
        return action(*args, **kwargs)
    except DirectoryUnavailableError as error:
        logger.warning("디렉터리 인증 실패: stage=%s", error.stage)
        raise


class LdapDirectoryAuthenticator:
    def __init__(self, connect: ConnectionFactory | None = None) -> None:
        self._connect = connect or default_connection_factory

    async def discover_base_dn(self, settings: DirectorySettings) -> str:
        return await asyncio.to_thread(_logged, self._discover, settings)

    async def authenticate(
        self, settings: DirectorySettings, base_dn: str, login_id: LoginId, password: Password
    ) -> DirectoryUser:
        secret = password.reveal()
        if not secret:
            # 빈 비밀번호는 익명 바인드로 통과될 수 있으므로 연결하지 않고 거부한다.
            raise InvalidCredentialsError(_INVALID_CREDENTIALS, stage=VerificationStage.BIND)
        return await asyncio.to_thread(
            _logged, self._authenticate, settings, base_dn, login_id.value, secret
        )

    def _discover(self, settings: DirectorySettings) -> str:
        with service_session(self._connect, settings) as connection:
            return _read_base_dn(connection)

    def _authenticate(
        self, settings: DirectorySettings, base_dn: str, login_id: str, secret: str
    ) -> DirectoryUser:
        with service_session(self._connect, settings) as connection:
            user_dn, user = _find_user(connection, settings, base_dn, login_id)
        self._bind_user(settings, user_dn, secret)
        return user

    def _bind_user(self, settings: DirectorySettings, user_dn: str, secret: str) -> None:
        connection = self._connect(settings, user_dn, secret)
        try:
            open_secure(connection, settings)
            if not guarded(connection.bind):
                raise bind_failure(_result_code(connection))
        finally:
            unbind(connection)
