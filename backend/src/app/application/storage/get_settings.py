from typing import TYPE_CHECKING

from app.domain.common.errors import NotFoundError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.storage.settings import StoredStorageSettings


class GetStorageSettings:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> StoredStorageSettings:
        async with self._uow_factory() as uow:
            stored = await uow.storage_settings.get()
        if stored is None:
            raise NotFoundError("파일 저장 위치", "storage")
        return stored
