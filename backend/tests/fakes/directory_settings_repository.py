from typing import TYPE_CHECKING

from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import StoredDirectorySettings

if TYPE_CHECKING:
    from app.application.ports.directory_settings_repository import DirectorySettingsWrite

_ROW = 1


class FakeDirectorySettingsRepository:
    def __init__(self) -> None:
        self._items: dict[int, StoredDirectorySettings] = {}

    async def get(self) -> StoredDirectorySettings | None:
        return self._items.get(_ROW)

    async def save(self, change: DirectorySettingsWrite) -> StoredDirectorySettings:
        current = self._items.get(_ROW)
        if change.expected_revision is None:
            if current is not None:
                raise DirectorySettingsConflictError
            revision = 1
        else:
            if current is None or current.revision != change.expected_revision:
                raise DirectorySettingsConflictError
            revision = current.revision + 1
        stored = StoredDirectorySettings(
            connection=change.connection,
            base_dn=change.base_dn,
            revision=revision,
            updated_at=change.now,
            updated_by=change.updated_by,
        )
        self._items[_ROW] = stored
        return stored
