"""Deal이 참조하는 고객·파트너가 존재하는지 확인한다. 삭제된 대상은 없는 것으로 본다."""

from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidReferenceError
from app.domain.customer.errors import CustomerNotFoundError
from app.domain.partner.errors import PartnerNotFoundError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.deal.value_objects import DealDetails


async def ensure_references_exist(uow: UnitOfWork, details: DealDetails) -> None:
    try:
        await uow.customers.get(details.customer_id)
    except CustomerNotFoundError as error:
        raise InvalidReferenceError("고객", details.customer_id) from error
    if details.partner_id is not None:
        try:
            await uow.partners.get(details.partner_id)
        except PartnerNotFoundError as error:
            raise InvalidReferenceError("파트너", details.partner_id) from error
