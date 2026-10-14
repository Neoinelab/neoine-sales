from typing import TYPE_CHECKING

from app.application.deal.references import ensure_references_exist
from app.application.user.assignment import ensure_assignable

if TYPE_CHECKING:
    from app.application.deal.inputs import DealInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from app.domain.deal.value_objects import DealId


class UpdateDeal:
    """Deal 정보를 전체 교체한다. 참조(고객·파트너)와 Deal Code 고유성을 다시 확인한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, deal_id: DealId, data: DealInput) -> Deal:
        details = data.to_details()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_id, for_update=True)
            await ensure_references_exist(uow, details)
            await ensure_assignable(
                uow, details.owner_user_id, unchanged_from=deal.details.owner_user_id
            )
            deal.update(details, self._clock.now())
            await uow.deals.update(deal)
            await uow.commit()
        return deal
