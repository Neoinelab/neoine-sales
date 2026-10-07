from typing import TYPE_CHECKING

from app.domain.deal.value_objects import DealCode

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal


class GetDealByCode:
    """업무 키(Deal Code)로 조회한다. 대소문자는 구분하지 않는다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, code: str) -> Deal:
        deal_code = DealCode(code)
        async with self._uow_factory() as uow:
            return await uow.deals.get_by_code(deal_code)
