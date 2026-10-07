from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal


class ListDeals:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Deal]:
        async with self._uow_factory() as uow:
            return await uow.deals.list(offset=offset, limit=limit)
