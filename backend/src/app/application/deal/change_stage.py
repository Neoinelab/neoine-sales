from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.deal.inputs import StageChangeInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from app.domain.deal.value_objects import DealId


class ChangeDealStage:
    """Deal의 단계를 바꾸고 이력을 남긴다. 한 트랜잭션이며 행을 잠가 from_stage를 보호한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, deal_id: DealId, data: StageChangeInput) -> Deal:
        changer = data.to_changer()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_id, for_update=True)
            change = deal.change_stage(
                data.stage, reason=data.reason, changed_by=changer, now=self._clock.now()
            )
            await uow.deals.update(deal)
            await uow.deal_stage_changes.add(change)
            await uow.commit()
        return deal
