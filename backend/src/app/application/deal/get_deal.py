from typing import TYPE_CHECKING

from app.application.deal.views import build_views
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class GetDeal:
    """Deal 상세. 없는 code와 형식이 틀린 code는 같은 DealNotFoundError다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, code: str) -> DealView:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        async with self._uow_factory() as uow:
            item = await uow.deals.get_item(deal_code)
            return (await build_views(uow, [item], now=self._clock.now()))[0]
