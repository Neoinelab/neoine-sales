from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.deal_action_repository import DealActionQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.entities import DealAction


class SearchDealActions:
    """조건에 맞는 활동을 최신순으로 찾는다.

    deal_id를 주면 그 Deal이 있어야 한다(없으면 DealNotFoundError).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: DealActionQuery) -> Sequence[DealAction]:
        async with self._uow_factory() as uow:
            if query.deal_id is not None:
                await uow.deals.get(query.deal_id)
            return await uow.deal_actions.search(query)
