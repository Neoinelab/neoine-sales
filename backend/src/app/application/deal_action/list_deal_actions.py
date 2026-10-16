from typing import TYPE_CHECKING

from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.deal_action_repository import DealActionQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.entities import DealAction


class ListDealActions:
    """한 Deal의 Action을 조건에 맞게 전부 돌려준다(페이지 없음). 없는 Deal은 DealNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: DealActionQuery) -> Sequence[DealAction]:
        async with self._uow_factory() as uow:
            if not await uow.deals.exists(query.deal_code):
                raise DealNotFoundError(query.deal_code.value)
            return await uow.deal_actions.search(query)
