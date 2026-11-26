"""AD 연결 테스트는 임시 계정으로 RootDSE를 읽고, 로그인은 사용자 UPN으로 바인드한다.

사용자 프로필은 같은 연결에서 조회한다. 자격증명은 요청 동안에만 사용하며 로그에 남기지 않는다.
동기 ldap3 호출은 작업 스레드에서 실행한다.
"""

import logging
from typing import TYPE_CHECKING, Any

import anyio
from ldap3 import BASE, SUBTREE, Connection
from ldap3.utils.conv import escape_filter_chars

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId
from app.domain.common.errors import InvalidValueError
from app.domain.directory import rules
from app.domain.directory.settings import (
    DISPLAY_NAME_ATTRIBUTE,
    EMAIL_ATTRIBUTE,
    DirectoryCredentials,
    DirectorySettings,
)
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

    from app.domain.auth.credentials import Password

__all__ = ["LdapDirectoryAuthenticator", "default_connection_factory"]

logger = logging.getLogger(__name__)

SEARCH_SIZE_LIMIT = 2  # 1건이 아니면 설정 오류이므로 2건까지만 받으면 판단할 수 있다
BASE_DN_MAX = 512
_INVALID_CREDENTIALS = "아이디 또는 비밀번호가 올바르지 않습니다"
_NAMING_CONTEXT = "defaultNamingContext"
_SUCCESS = 0
_SIZE_LIMIT_EXCEEDED = 4

_MOBILE_ATTRIBUTE = "mobile"
_TELEPHONE_ATTRIBUTE = "telephoneNumber"


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
            attributes=[
                DISPLAY_NAME_ATTRIBUTE,
                EMAIL_ATTRIBUTE,
                _MOBILE_ATTRIBUTE,
                _TELEPHONE_ATTRIBUTE,
            ],
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
        phone=_first(attributes, _MOBILE_ATTRIBUTE) or _first(attributes, _TELEPHONE_ATTRIBUTE),
    )
    return str(entries[0]["dn"]), user


def bind_account_name(account: str, domain: str | None) -> str:
    account = account.strip()
    if "@" in account or "\\" in account or "=" in account:
        return account
    if not domain:
        raise DirectoryMisconfiguredError(
            "AD 로그인 도메인이 설정되지 않았습니다.", stage=VerificationStage.BIND
        )
    return f"{account}@{domain}"


def _logged[**P, T](action: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    try:
        return action(*args, **kwargs)
    except DirectoryUnavailableError as error:
        logger.warning("디렉터리 인증 실패: stage=%s", error.stage)
        raise


class LdapDirectoryAuthenticator:
    def __init__(
        self, connect: ConnectionFactory | None = None, *, user_bind_domain: str | None = None
    ) -> None:
        self._connect = connect or default_connection_factory
        self._user_bind_domain = user_bind_domain

    @property
    def user_bind_domain(self) -> str | None:
        return self._user_bind_domain

    async def discover_base_dn(self, settings: DirectorySettings) -> str:
        return await anyio.to_thread.run_sync(_logged, self._discover, settings)

    async def authenticate(
        self, settings: DirectorySettings, base_dn: str, login_id: LoginId, password: Password
    ) -> DirectoryUser:
        try:
            login_id = LoginId(login_id.value)
        except InvalidValueError:
            raise InvalidCredentialsError(
                _INVALID_CREDENTIALS, stage=VerificationStage.BIND
            ) from None
        secret = password.reveal()
        if not secret:
            # 빈 비밀번호는 익명 바인드로 통과될 수 있으므로 연결하지 않고 거부한다.
            raise InvalidCredentialsError(_INVALID_CREDENTIALS, stage=VerificationStage.BIND)
        return await anyio.to_thread.run_sync(
            _logged, self._authenticate, settings, base_dn, login_id.value, secret
        )

    def _discover(self, settings: DirectorySettings) -> str:
        credentials = settings.credentials
        if credentials is None:
            raise InvalidValueError("연결 테스트 계정과 비밀번호를 입력하세요.")
        tested = DirectorySettings(
            settings.connection,
            DirectoryCredentials(
                bind_account_name(credentials.account, self._user_bind_domain), credentials.password
            ),
        )
        with service_session(self._connect, tested) as connection:
            return _read_base_dn(connection)

    def _authenticate(
        self, settings: DirectorySettings, base_dn: str, login_id: str, secret: str
    ) -> DirectoryUser:
        bind_name = bind_account_name(login_id, self._user_bind_domain)
        connection = self._connect(settings, bind_name, secret)
        try:
            open_secure(connection, settings)
            if not guarded(connection.bind):
                raise bind_failure(_result_code(connection))
            _, user = _find_user(connection, settings, base_dn, login_id)
            return user
        finally:
            unbind(connection)
