from typing import TYPE_CHECKING

from app.application.deal.references import ensure_references_exist
from app.domain.deal.entities import Deal

if TYPE_CHECKING:
    from app.application.deal.inputs import DealInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class RegisterDeal:
    """Deal을 등록한다. 고객(필수)과 파트너(지정 시)가 없으면 InvalidReferenceError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, data: DealInput, *, owner_user_id: str | None = None) -> Deal:
        details = data.to_details()
        async with self._uow_factory() as uow:
            await ensure_references_exist(uow, details)
            deal = Deal.create(details, self._clock.now(), owner_user_id=owner_user_id)
            await uow.deals.add(deal)
            await uow.commit()
        return deal
