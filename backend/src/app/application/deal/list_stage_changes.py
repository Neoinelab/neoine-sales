from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.stage import DealStageChange


class ListDealStageChanges:
    """Deal의 단계 변경 이력을 최신순으로 돌려준다. 삭제된 Deal의 이력도 조회된다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: DealStageChangeQuery) -> Sequence[DealStageChange]:
        async with self._uow_factory() as uow:
            await uow.deals.get(query.deal_id, include_deleted=True)
            return await uow.deal_stage_changes.search(query)
