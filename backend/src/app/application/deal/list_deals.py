from typing import TYPE_CHECKING

from app.application.deal.dto import DealPage
from app.application.deal.views import build_views

if TYPE_CHECKING:
    from app.application.ports.deal_repository import DealQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListDeals:
    """조건에 맞는 Deal 한 페이지와 페이지와 무관한 전체 건수."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: DealQuery) -> DealPage:
        start, end = query.revenue_window()
        if start is not None and end is not None and start > end:
            return DealPage(items=[], total=0, offset=query.offset, limit=query.limit)
        async with self._uow_factory() as uow:
            items = await uow.deals.search(query)
            total = await uow.deals.count(query)
            views = await build_views(uow, items)
        return DealPage(items=views, total=total, offset=query.offset, limit=query.limit)
