from typing import TYPE_CHECKING

from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from app.application.ports.deal_repository import DealDeletionImpact
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class GetDealDeletionImpact:
    """삭제하면 함께 지워지는 데이터 건수. 없는 code와 형식이 틀린 code는 DealNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, code: str) -> DealDeletionImpact:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        async with self._uow_factory() as uow:
            return await uow.deals.deletion_impact(deal_code)
