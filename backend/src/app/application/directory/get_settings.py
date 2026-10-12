from typing import TYPE_CHECKING

from app.domain.common.errors import NotFoundError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import StoredDirectorySettings


class GetDirectorySettings:
    """저장된 AD 설정을 돌려준다. 없으면 NotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> StoredDirectorySettings:
        async with self._uow_factory() as uow:
            stored = await uow.directory_settings.get()
        if stored is None:
            raise NotFoundError("AD 설정", "directory")
        return stored
