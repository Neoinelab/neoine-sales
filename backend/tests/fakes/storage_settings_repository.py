"""StorageSettingsRepository Port의 InMemory 구현(Fake). 단일 행(id=1), 마지막 저장이 이긴다.

도메인 모듈은 저장 시점에 가져온다(저장 위치 구현 전에도 이 Fake를 쓰는 다른 테스트가 수집된다).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.storage.path import StoragePath
    from app.domain.storage.settings import StoredStorageSettings
    from app.domain.user.value_objects import UserId

_ROW = 1


class FakeStorageSettingsRepository:
    def __init__(self) -> None:
        self._items: dict[int, StoredStorageSettings] = {}

    async def get(self) -> StoredStorageSettings | None:
        return self._items.get(_ROW)

    async def save(
        self, path: StoragePath, *, updated_by: UserId | None, now: datetime
    ) -> StoredStorageSettings:
        from app.domain.storage.settings import StoredStorageSettings  # noqa: PLC0415

        stored = StoredStorageSettings(path=path, updated_at=now, updated_by=updated_by)
        self._items[_ROW] = stored  # 값 객체(frozen)라 복사가 필요 없다
        return stored
