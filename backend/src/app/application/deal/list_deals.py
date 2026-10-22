from typing import TYPE_CHECKING

from app.application.deal.dto import DealPage
from app.application.deal.views import build_views, load_thresholds
from app.domain.common.business_date import business_date
from app.domain.deal.risk import RiskBasis

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.deal_repository import DealQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListDeals:
    """조건에 맞는 Deal 한 페이지와 페이지와 무관한 전체 건수."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, query: DealQuery) -> DealPage:
        now = self._clock.now()
        today = business_date(now)
        query = query.with_year_for(today)
        async with self._uow_factory() as uow:
            thresholds = await load_thresholds(uow)  # 필터와 응답 risk가 같은 기준을 쓴다
            query = query.with_risk_basis(RiskBasis(today, thresholds.stale_days))
            items = await uow.deals.search(query)
            total = await uow.deals.count(query)
            views = await build_views(uow, items, now=now, thresholds=thresholds)
        return DealPage(items=views, total=total, offset=query.offset, limit=query.limit)
