from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.partner.value_objects import PartnerId


class DeletePartner:
    """파트너를 소프트 삭제한다. 이미 삭제됐거나 없으면 PartnerNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, partner_id: PartnerId) -> None:
        async with self._uow_factory() as uow:
            partner = await uow.partners.get(partner_id)
            partner.soft_delete(self._clock.now())
            await uow.partners.update(partner)
            await uow.commit()
