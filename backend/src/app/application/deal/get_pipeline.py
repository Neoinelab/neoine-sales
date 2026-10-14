from typing import TYPE_CHECKING

from app.domain.deal.pipeline import DealPipeline

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserId


class GetDealPipeline:
    """단계별 건수와 통화별 매출 합계."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, owner_user_id: UserId | None = None) -> DealPipeline:
        async with self._uow_factory() as uow:
            totals = await uow.deals.summarize_pipeline(owner_user_id=owner_user_id)
            return DealPipeline.from_totals(totals)
