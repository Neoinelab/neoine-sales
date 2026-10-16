from typing import TYPE_CHECKING

from app.application.contact.dto import ContactPage, ContactUsage
from app.application.contact.usage import with_deal_counts

if TYPE_CHECKING:
    from app.application.ports.contact_repository import ContactQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory

__all__ = ["ContactPage", "ContactUsage", "SearchContacts"]


class SearchContacts:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ContactQuery) -> ContactPage:
        async with self._uow_factory() as uow:
            found = await uow.contacts.search(query)
            total = await uow.contacts.count(query)
            items = await with_deal_counts(uow, found)
        return ContactPage(items=items, total=total, offset=query.offset, limit=query.limit)
