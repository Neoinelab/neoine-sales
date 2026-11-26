from typing import TYPE_CHECKING

from pydantic import BaseModel, SecretStr, StrictInt

from app.domain.common.secret import SealedSecret
from app.domain.directory.settings import (
    DirectoryConnection,
    DirectoryCredentials,
    DirectorySettings,
    DirectorySettingsDraft,
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
    host: str
    port: StrictInt
    security: SecurityMode
    user_filter: str
    connect_timeout_seconds: StrictInt = 5

    def to_connection(self) -> DirectoryConnection:
        return DirectoryConnection(
            host=self.host,
            port=self.port,
            security=self.security,
            user_filter=self.user_filter,
            connect_timeout_seconds=self.connect_timeout_seconds,
        )


class DirectorySettingsRequest(DirectoryConnectionRequest):
    bind_account: SecretStr
    bind_password: SecretStr

    def to_domain(self) -> DirectorySettings:
        return DirectorySettings(
            self.to_connection(),
            DirectoryCredentials(
                self.bind_account.get_secret_value(),
                bind_password_of(self.bind_password.get_secret_value()),
            ),
        )


class DirectorySettingsSaveRequest(DirectoryConnectionRequest):
    test_token: SecretStr

    def to_draft(self) -> DirectorySettingsDraft:
        return DirectorySettingsDraft(
            self.to_connection(), SealedSecret(self.test_token.get_secret_value())
        )


class DirectorySettingsResponse(BaseModel):
    host: str
    port: int
    security: SecurityMode
    user_filter: str
    connect_timeout_seconds: int
    base_dn: str
    revision: int
    updated_at: ServerDateTime
    updated_by: UserRef | None

    @classmethod
    def from_stored(
        cls, stored: StoredDirectorySettings, refs: Mapping[UserId, DomainUserRef]
    ) -> DirectorySettingsResponse:
        connection = stored.connection
        return cls(
            host=connection.host,
            port=connection.port,
            security=connection.security,
            user_filter=connection.user_filter,
            connect_timeout_seconds=connection.connect_timeout_seconds,
            base_dn=stored.base_dn,
            revision=stored.revision,
            updated_at=stored.updated_at,
            updated_by=None if stored.updated_by is None else ref_of(refs, stored.updated_by),
        )


async def directory_response(
    provider: UseCaseProvider, stored: StoredDirectorySettings
) -> DirectorySettingsResponse:
    refs = await resolve_refs(provider, [stored.updated_by])
    return DirectorySettingsResponse.from_stored(stored, refs)
