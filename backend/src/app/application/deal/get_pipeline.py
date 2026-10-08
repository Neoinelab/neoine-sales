from typing import TYPE_CHECKING

from app.application.ports.deal_repository import normalize_owner_user_id
from app.domain.deal.pipeline import DealPipeline

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class GetDealPipeline:
    """단계별 건수와 통화별 매출 합계(삭제된 Deal 제외)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, owner_user_id: str | None = None) -> DealPipeline:
        owner = normalize_owner_user_id(owner_user_id)
        async with self._uow_factory() as uow:
            totals = await uow.deals.summarize_pipeline(owner_user_id=owner)
            return DealPipeline.from_totals(totals)
