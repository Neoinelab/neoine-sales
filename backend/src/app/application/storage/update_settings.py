from typing import TYPE_CHECKING

from app.application.storage.probe import ensure_writable
from app.domain.storage.path import StoragePath

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.storage.settings import StoredStorageSettings


class UpdateStorageSettings:
    """admin이 저장 위치를 바꾼다. 쓰기 확인을 통과해야 저장한다(기존 파일은 옮기지 않는다)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(self, *, actor: Principal, raw_path: str) -> StoredStorageSettings:
        path = StoragePath.parse(raw_path)
        await ensure_writable(self._storage, path)
        async with self._uow_factory() as uow:
            stored = await uow.storage_settings.save(
                path, updated_by=actor.user_id, now=self._clock.now()
            )
            await uow.commit()
        return stored
