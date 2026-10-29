from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 (dataclass 필드 타입)
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError
from app.domain.common.secret import SealedSecret  # noqa: TC001 (dataclass 필드 타입)
from app.domain.directory import rules
from app.domain.directory.host import normalize_host
from app.domain.user.value_objects import UserId  # noqa: TC001 (dataclass 필드 타입)

if TYPE_CHECKING:
    from collections.abc import Mapping


class SecurityMode(StrEnum):
    NONE = "none"  # 평문 LDAP
    SSL = "ssl"  # LDAPS(접속 즉시 TLS)
    STARTTLS = "starttls"  # 평문 접속 후 StartTLS


DEFAULT_PORTS: Mapping[SecurityMode, int] = MappingProxyType(
    {SecurityMode.NONE: 389, SecurityMode.SSL: 636, SecurityMode.STARTTLS: 389}
)
RECEIVE_TIMEOUT_SECONDS = 10
DISPLAY_NAME_ATTRIBUTE = "displayName"
EMAIL_ATTRIBUTE = "mail"

PORT_MAX = 65535
BASE_DN_MAX = 512


@dataclass(frozen=True, slots=True)
class DirectoryConnection:
    """비밀이 아닌 접속 정보. 생성할 때 모든 필드를 검증한다."""

    host: str
    port: int
    security: SecurityMode
    bind_account: str
    user_filter: str
    connect_timeout_seconds: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", normalize_host(self.host))
        rules.check_range(self.port, "port", low=1, high=PORT_MAX)
        rules.check_text(self.bind_account, "bind_account", max_length=rules.BIND_ACCOUNT_MAX)
        rules.check_filter(self.user_filter, "user_filter")
        rules.check_range(self.connect_timeout_seconds, "connect_timeout_seconds", low=1, high=30)

    def same_endpoint_and_account(self, other: DirectoryConnection) -> bool:
        """host·port·security·bind_account가 모두 같으면 True(저장된 비밀번호 재사용 판단)."""
        return (self.host, self.port, self.security, self.bind_account) == (
            other.host,
            other.port,
            other.security,
            other.bind_account,
        )


@dataclass(frozen=True, slots=True)
class DirectorySettings:
    """AD 접속에 필요한 전부(평문 비밀번호 포함). repr에 비밀번호가 나오지 않는다."""

    connection: DirectoryConnection
    bind_password: Password


def bind_password_of(raw: str) -> Password:
    """바인드 비밀번호를 만든다. 위반 메시지 앞에 필드 이름을 붙인다."""
    try:
        return Password(raw)
    except InvalidValueError as error:
        raise InvalidValueError(f"bind_password: {error}") from None


@dataclass(frozen=True, slots=True)
class DirectorySettingsDraft:
    """화면에서 받은 후보. bind_password=None이면 '저장된 값 유지' 요청이다."""

    connection: DirectoryConnection
    bind_password: Password | None

    def complete(
        self, previous: DirectoryConnection | None, previous_password: Password | None
    ) -> DirectorySettings:
        """새 비밀번호가 있으면 그것을 쓴다. 없으면 접속 정보가 저장 값과 같고 저장 비밀번호를 읽을
        수 있을 때만 저장된 비밀번호를 쓴다(저장된 비밀번호가 다른 서버로 가는 것을 막는다)."""
        if self.bind_password is not None:
            return DirectorySettings(self.connection, self.bind_password)
        if previous is None:
            raise InvalidValueError("bind_password: 바인드 비밀번호를 입력하세요")
        if not self.connection.same_endpoint_and_account(previous):
            raise InvalidValueError(
                "bind_password: 서버나 바인드 계정을 바꾸면 비밀번호를 다시 입력해야 합니다"
            )
        if previous_password is None:
            raise InvalidValueError(
                "bind_password: 저장된 비밀번호를 읽을 수 없습니다. 다시 입력하세요"
            )
        return DirectorySettings(self.connection, previous_password)


@dataclass(frozen=True, slots=True)
class StoredDirectorySettings:
    """저장된 설정(단일 행). revision은 1부터 저장할 때마다 +1, 최초 설정이면 updated_by는 None."""

    connection: DirectoryConnection
    sealed_bind_password: SealedSecret
    base_dn: str
    revision: int
    updated_at: datetime
    updated_by: UserId | None

    def __post_init__(self) -> None:
        rules.check_text(self.base_dn, "base_dn", max_length=BASE_DN_MAX)
