from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError
from app.domain.directory import rules
from app.domain.directory.host import normalize_host

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from app.domain.common.secret import SealedSecret
    from app.domain.user.value_objects import UserId


class SecurityMode(StrEnum):
    NONE = "none"
    SSL = "ssl"
    STARTTLS = "starttls"


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
    host: str
    port: int
    security: SecurityMode
    user_filter: str
    connect_timeout_seconds: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", normalize_host(self.host))
        rules.check_range(self.port, "port", low=1, high=PORT_MAX)
        rules.check_filter(self.user_filter, "user_filter")
        rules.check_range(self.connect_timeout_seconds, "connect_timeout_seconds", low=1, high=30)


@dataclass(frozen=True, slots=True, repr=False)
class DirectoryCredentials:
    account: str
    password: Password

    def __post_init__(self) -> None:
        rules.check_text(self.account, "bind_account", max_length=rules.BIND_ACCOUNT_MAX)


@dataclass(frozen=True, slots=True)
class DirectorySettings:
    connection: DirectoryConnection
    credentials: DirectoryCredentials | None = None


def bind_password_of(raw: str) -> Password:
    try:
        return Password(raw)
    except InvalidValueError as error:
        raise InvalidValueError(f"bind_password: {error}") from None


@dataclass(frozen=True, slots=True)
class DirectorySettingsDraft:
    connection: DirectoryConnection
    test_token: SealedSecret


@dataclass(frozen=True, slots=True)
class StoredDirectorySettings:
    connection: DirectoryConnection
    base_dn: str
    revision: int
    updated_at: datetime
    updated_by: UserId | None

    def __post_init__(self) -> None:
        rules.check_text(self.base_dn, "base_dn", max_length=BASE_DN_MAX)
