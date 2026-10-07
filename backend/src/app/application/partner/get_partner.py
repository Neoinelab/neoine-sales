from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.partner.entities import Partner
    from app.domain.partner.value_objects import PartnerId


class GetPartner:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, partner_id: PartnerId) -> Partner:
        async with self._uow_factory() as uow:
            return await uow.partners.get(partner_id)
