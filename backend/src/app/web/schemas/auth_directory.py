from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, SecretStr, StrictInt

from app.domain.directory.settings import (
    DirectoryConnection,
    DirectorySettings,
    SecurityMode,
    StoredDirectorySettings,
    bind_password_of,
)
from app.web.schemas.common import RequestModel
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class DirectoryConnectionRequest(RequestModel):
    """AD 접속 정보(비밀번호 제외). 값 검증은 도메인이 하며 메시지에 필드 이름이 들어간다."""

    host: str
    port: StrictInt
    security: SecurityMode
    bind_account: str
    user_filter: str
    connect_timeout_seconds: StrictInt = 5

    def to_connection(self) -> DirectoryConnection:
        return DirectoryConnection(
            host=self.host,
            port=self.port,
            security=self.security,
            bind_account=self.bind_account,
            user_filter=self.user_filter,
            connect_timeout_seconds=self.connect_timeout_seconds,
        )


class DirectorySettingsRequest(DirectoryConnectionRequest):
    """최초 설정 본문: 바인드 비밀번호 필수."""

    bind_password: SecretStr

    def to_domain(self) -> DirectorySettings:
        return DirectorySettings(
            self.to_connection(), bind_password_of(self.bind_password.get_secret_value())
        )


class DirectorySettingsResponse(BaseModel):
    """저장된 설정. 비밀번호는 어떤 형태로도 담지 않는다."""

    host: str
    port: int
    security: SecurityMode
    bind_account: str
    bind_credential_status: Literal["ok", "unreadable"]
    user_filter: str
    connect_timeout_seconds: int
    base_dn: str
    revision: int
    updated_at: ServerDateTime
    updated_by: UserRef | None

    @classmethod
    def from_stored(
        cls,
        stored: StoredDirectorySettings,
        refs: Mapping[UserId, DomainUserRef],
        *,
        credential_readable: bool = True,
    ) -> DirectorySettingsResponse:
        c = stored.connection
        updated_by = None if stored.updated_by is None else ref_of(refs, stored.updated_by)
        return cls(
            host=c.host,
            port=c.port,
            security=c.security,
            bind_account=c.bind_account,
            bind_credential_status="ok" if credential_readable else "unreadable",
            user_filter=c.user_filter,
            connect_timeout_seconds=c.connect_timeout_seconds,
            base_dn=stored.base_dn,
            revision=stored.revision,
            updated_at=stored.updated_at,
            updated_by=updated_by,
        )


async def directory_response(
    provider: UseCaseProvider, stored: StoredDirectorySettings, *, credential_readable: bool = True
) -> DirectorySettingsResponse:
    """저장자(updated_by) 표시 이름을 풀어 응답으로 만든다."""
    refs = await resolve_refs(provider, [stored.updated_by])
    return DirectorySettingsResponse.from_stored(
        stored, refs, credential_readable=credential_readable
    )
