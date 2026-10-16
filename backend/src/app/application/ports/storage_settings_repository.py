from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.storage.path import StoragePath
    from app.domain.storage.settings import StoredStorageSettings
    from app.domain.user.value_objects import UserId


class StorageSettingsRepository(Protocol):
    async def get(self) -> StoredStorageSettings | None: ...

    async def save(
        self, path: StoragePath, *, updated_by: UserId | None, now: datetime
    ) -> StoredStorageSettings:
        """단일 행 upsert. 마지막 저장이 이긴다(updated_by=None으로 덮어쓰면 저장자도 비운다)."""
        ...
