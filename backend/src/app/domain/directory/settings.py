from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 (dataclass 필드 타입)

from app.domain.common.errors import InvalidValueError
from app.domain.directory import rules
from app.domain.directory.url import DirectoryUrl
from app.domain.user.value_objects import UserId  # noqa: TC001 (dataclass 필드 타입)

__all__ = ["DirectorySettings", "DirectoryUrl", "StoredDirectorySettings"]

MAX_SERVERS = 5


@dataclass(frozen=True, slots=True)
class DirectorySettings:
    """AD 서버 접속 설정. 비밀 값은 없다(사용자 자기 자격증명으로 바인드한다)."""

    server_urls: tuple[DirectoryUrl, ...]
    use_starttls: bool
    ca_cert_pem: str | None
    bind_template: str
    base_dn: str
    user_filter: str
    display_name_attribute: str = "displayName"
    email_attribute: str = "mail"
    connect_timeout_seconds: int = 5
    receive_timeout_seconds: int = 10

    def __post_init__(self) -> None:
        self._check_servers()
        rules.check_template(self.bind_template, "bind_template", max_length=rules.TEMPLATE_MAX)
        rules.check_text(self.base_dn, "base_dn", max_length=rules.DN_FILTER_MAX)
        rules.check_filter(self.user_filter, "user_filter")
        rules.check_attribute(self.display_name_attribute, "display_name_attribute")
        rules.check_attribute(self.email_attribute, "email_attribute")
        rules.check_pem(self.ca_cert_pem, "ca_cert_pem")
        rules.check_range(self.connect_timeout_seconds, "connect_timeout_seconds", low=1, high=30)
        rules.check_range(self.receive_timeout_seconds, "receive_timeout_seconds", low=1, high=60)

    def _check_servers(self) -> None:
        if not 1 <= len(self.server_urls) <= MAX_SERVERS:
            raise InvalidValueError(f"server_urls는 1~{MAX_SERVERS}개여야 합니다")
        if len(set(self.server_urls)) != len(self.server_urls):
            raise InvalidValueError("server_urls에 같은 주소를 중복해 넣을 수 없습니다")
        if not self.use_starttls and any(url.scheme == "ldap" for url in self.server_urls):
            raise InvalidValueError("ldap:// 주소를 쓰려면 use_starttls를 켜야 합니다")

    @property
    def bind_template_is_dn(self) -> bool:
        return rules.is_dn_template(self.bind_template)


@dataclass(frozen=True, slots=True)
class StoredDirectorySettings:
    """저장된 설정(단일 행). revision은 1부터 저장할 때마다 +1, setup이면 updated_by는 None."""

    settings: DirectorySettings
    revision: int
    updated_at: datetime
    updated_by: UserId | None
