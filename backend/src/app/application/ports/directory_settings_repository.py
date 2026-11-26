from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.directory.settings import DirectoryConnection, StoredDirectorySettings
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class DirectorySettingsWrite:
    connection: DirectoryConnection
    base_dn: str
    expected_revision: int | None
    updated_by: UserId | None
    now: datetime


class DirectorySettingsRepository(Protocol):
    async def get(self) -> StoredDirectorySettings | None: ...

    async def save(self, change: DirectorySettingsWrite) -> StoredDirectorySettings: ...
