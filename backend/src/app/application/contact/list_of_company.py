from typing import TYPE_CHECKING

from app.application.contact.usage import with_deal_counts

if TYPE_CHECKING:
    from app.application.contact.dto import ContactUsage
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.contact.values import ContactKind


class ListContactsOfCompany:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, kind: ContactKind, company: str) -> list[ContactUsage]:
        async with self._uow_factory() as uow:
            found = await uow.contacts.of_company(kind, company)
            return await with_deal_counts(uow, found)
