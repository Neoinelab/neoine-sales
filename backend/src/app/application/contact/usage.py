from typing import TYPE_CHECKING

from app.application.contact.dto import ContactUsage

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.contact.entities import Contact


async def with_deal_counts(uow: UnitOfWork, contacts: Sequence[Contact]) -> list[ContactUsage]:
    """연락처마다 참조하는 Deal 수를 한 번의 조회로 붙인다."""
    counts = await uow.deals.count_by_contacts([c.id for c in contacts])
    return [ContactUsage(contact=c, deal_count=counts.get(c.id, 0)) for c in contacts]
