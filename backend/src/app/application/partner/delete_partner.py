from typing import TYPE_CHECKING

from app.domain.partner.errors import PartnerInUseError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.partner.value_objects import PartnerId


class DeletePartner:
    """파트너를 물리 삭제한다. 없으면 NotFound, 참조하는 Deal이 있으면 PartnerInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, partner_id: PartnerId) -> None:
        async with self._uow_factory() as uow:
            await uow.partners.get(partner_id)
            if await uow.deals.exists_for_partner(partner_id):
                raise PartnerInUseError(partner_id)
            await uow.partners.delete(partner_id)
            await uow.commit()
