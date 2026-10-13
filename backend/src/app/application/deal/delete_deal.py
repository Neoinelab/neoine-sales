from typing import TYPE_CHECKING

from app.domain.deal.errors import DealInUseError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.value_objects import DealId


class DeleteDeal:
    """Deal을 물리 삭제한다. 활동 또는 단계 변경 이력이 있으면 DealInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, deal_id: DealId) -> None:
        async with self._uow_factory() as uow:
            await uow.deals.get(deal_id, for_update=True)
            if await uow.deal_actions.exists_for_deal(
                deal_id
            ) or await uow.deal_stage_changes.exists_for_deal(deal_id):
                raise DealInUseError(deal_id)
            await uow.deals.delete(deal_id)
            await uow.commit()
