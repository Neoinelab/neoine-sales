from typing import TYPE_CHECKING

from app.domain.partner.entities import Partner

if TYPE_CHECKING:
    from app.application.partner.inputs import PartnerInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class RegisterPartner:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, data: PartnerInput) -> Partner:
        details = data.to_details()
        async with self._uow_factory() as uow:
            partner = Partner.create(details, self._clock.now())
            await uow.partners.add(partner)
            await uow.commit()
        return partner
