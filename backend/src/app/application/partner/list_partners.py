from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.partner_repository import PartnerQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.partner.entities import Partner


class ListPartners:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: PartnerQuery) -> Sequence[Partner]:
        async with self._uow_factory() as uow:
            return await uow.partners.search(query)
