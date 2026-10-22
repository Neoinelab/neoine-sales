"""Dashboard 집계: Deal 원장에서 Status별·분기별 건수·금액을 바로 읽는다.

조건은 Deal 목록과 같은 `deal_search.conditions`를 쓰므로 목록(원장)과 항상 일치한다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import extract, func, select

from app.domain.dashboard.quarter_closing import QuarterBucket
from app.domain.forecast.summary import Tally
from app.infra.db.deal_search import conditions
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.ports.deal_repository import DealQuery

_AMOUNT = func.coalesce(func.sum(DealRow.revenue_amount), 0)


class SqlDashboardTallyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def tally_by_status(self, query: DealQuery) -> Mapping[str, Tally]:
        statement = (
            select(DealRow.status_key, func.count(), _AMOUNT)
            .where(*conditions(query))
            .group_by(DealRow.status_key)
        )
        result = await self._session.execute(statement)
        return {key: Tally(int(count), int(amount)) for key, count, amount in result}

    async def tally_by_quarter(self, query: DealQuery) -> Sequence[QuarterBucket]:
        if query.year is None or query.quarter is not None or query.month is not None:
            raise ValueError("분기별 집계는 연 단위 질의(year만)에서만 쓸 수 있습니다.")
        month = extract("month", DealRow.revenue_date)
        statement = (
            select(month, DealRow.forecast_key, func.count(), _AMOUNT)
            .where(*conditions(query))
            .group_by(month, DealRow.forecast_key)
        )
        result = await self._session.execute(statement)
        quarters: dict[tuple[int, str], Tally] = {}
        for m, forecast_key, count, amount in result:
            key = ((int(m) - 1) // 3 + 1, forecast_key)
            quarters[key] = quarters.get(key, Tally.ZERO).add(Tally(int(count), int(amount)))
        return [QuarterBucket(q, key, tally) for (q, key), tally in quarters.items()]
