from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.partner.inputs import PartnerInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.partner.entities import Partner
    from app.domain.partner.value_objects import PartnerId


class UpdatePartner:
    """파트너 정보를 전체 교체한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, partner_id: PartnerId, data: PartnerInput) -> Partner:
        details = data.to_details()
        async with self._uow_factory() as uow:
            partner = await uow.partners.get(partner_id)
            partner.update(details, self._clock.now())
            await uow.partners.update(partner)
            await uow.commit()
        return partner
