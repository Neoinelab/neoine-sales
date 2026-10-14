from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings
from app.domain.directory.url import DEFAULT_PORTS, DirectoryUrl
from app.web.schemas.common import RequestModel
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


def _format_url(url: DirectoryUrl) -> str:
    """기본 포트는 생략해 보여 준다(ldaps 636, ldap 389)."""
    host = f"[{url.host}]" if ":" in url.host else url.host
    port = "" if url.port == DEFAULT_PORTS[url.scheme] else f":{url.port}"
    return f"{url.scheme}://{host}{port}"


class DirectorySettingsRequest(RequestModel):
    """AD 서버 설정. 값 검증은 도메인(DirectorySettings)이 하고 메시지에 필드 이름이 들어간다."""

    server_urls: list[str]
    use_starttls: bool
    ca_cert_pem: str | None = None
    bind_template: str
    base_dn: str
    user_filter: str
    display_name_attribute: str = "displayName"
    email_attribute: str = "mail"
    connect_timeout_seconds: int = 5
    receive_timeout_seconds: int = 10

    def to_domain(self) -> DirectorySettings:
        return DirectorySettings(
            server_urls=tuple(DirectoryUrl.parse(text) for text in self.server_urls),
            use_starttls=self.use_starttls,
            ca_cert_pem=self.ca_cert_pem,
            bind_template=self.bind_template,
            base_dn=self.base_dn,
            user_filter=self.user_filter,
            display_name_attribute=self.display_name_attribute,
            email_attribute=self.email_attribute,
            connect_timeout_seconds=self.connect_timeout_seconds,
            receive_timeout_seconds=self.receive_timeout_seconds,
        )


class DirectorySettingsResponse(BaseModel):
    server_urls: list[str]
    use_starttls: bool
    ca_cert_pem: str | None
    bind_template: str
    base_dn: str
    user_filter: str
    display_name_attribute: str
    email_attribute: str
    connect_timeout_seconds: int
    receive_timeout_seconds: int
    revision: int
    updated_at: datetime
    updated_by: UserRef | None

    @classmethod
    def from_stored(
        cls, stored: StoredDirectorySettings, refs: Mapping[UserId, DomainUserRef]
    ) -> DirectorySettingsResponse:
        s = stored.settings
        updated_by = None if stored.updated_by is None else ref_of(refs, stored.updated_by)
        return cls(
            server_urls=[_format_url(url) for url in s.server_urls],
            use_starttls=s.use_starttls,
            ca_cert_pem=s.ca_cert_pem,
            bind_template=s.bind_template,
            base_dn=s.base_dn,
            user_filter=s.user_filter,
            display_name_attribute=s.display_name_attribute,
            email_attribute=s.email_attribute,
            connect_timeout_seconds=s.connect_timeout_seconds,
            receive_timeout_seconds=s.receive_timeout_seconds,
            revision=stored.revision,
            updated_at=stored.updated_at,
            updated_by=updated_by,
        )


async def directory_response(
    provider: UseCaseProvider, stored: StoredDirectorySettings
) -> DirectorySettingsResponse:
    """저장자(updated_by) 표시 이름을 풀어 응답으로 만든다."""
    refs = await resolve_refs(provider, [stored.updated_by])
    return DirectorySettingsResponse.from_stored(stored, refs)
