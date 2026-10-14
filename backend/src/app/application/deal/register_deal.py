from typing import TYPE_CHECKING

from app.application.deal.references import ensure_references_exist
from app.application.user.assignment import ensure_assignable
from app.domain.deal.entities import Deal

if TYPE_CHECKING:
    from app.application.deal.inputs import DealInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserId


class RegisterDeal:
    """Deal을 등록한다. 고객(필수)·파트너(지정 시)·담당자(재직자)가 없으면 InvalidReferenceError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, data: DealInput, *, registered_by_user_id: UserId | None = None
    ) -> Deal:
        details = data.to_details()
        async with self._uow_factory() as uow:
            await ensure_references_exist(uow, details)
            await ensure_assignable(uow, details.owner_user_id)
            deal = Deal.create(
                details, self._clock.now(), registered_by_user_id=registered_by_user_id
            )
            await uow.deals.add(deal)
            await uow.commit()
        return deal
