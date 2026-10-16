from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.contact.values import ContactKind


class ListContactCompanies:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, kind: ContactKind) -> list[str]:
        async with self._uow_factory() as uow:
            return list(await uow.contacts.companies(kind))
