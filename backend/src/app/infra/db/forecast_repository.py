"""Forecast 집계: Deal 원장에서 (담당자, Forecast key)별 건수·금액을 바로 읽는다.

월말 스냅숏 저장소(`SqlForecastSnapshotRepository`)도 여기서 내보낸다(구현은 별도 모듈).

조건은 Deal 목록과 같은 `deal_search.conditions`를 쓰므로 원장과 항상 일치한다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import extract, func, select

from app.application.ports.forecast_repository import MonthlyBucket
from app.domain.forecast.summary import ForecastBucket, Tally
from app.domain.user.value_objects import UserId
from app.infra.db.deal_search import conditions
from app.infra.db.forecast_snapshot_repository import SqlForecastSnapshotRepository
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.ports.forecast_repository import ForecastCriteria


__all__ = ["SqlForecastSnapshotRepository", "SqlForecastTallyRepository"]


class SqlForecastTallyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def tally(self, criteria: ForecastCriteria) -> Sequence[ForecastBucket]:
        statement = (
            select(
                DealRow.owner_user_id,
                DealRow.forecast_key,
                func.count(),
                func.coalesce(func.sum(DealRow.revenue_amount), 0),
            )
            .where(*conditions(criteria.to_deal_query()))
            .group_by(DealRow.owner_user_id, DealRow.forecast_key)
        )
        result = await self._session.execute(statement)
        return [
            ForecastBucket(UserId(owner), forecast_key, Tally(int(count), int(amount)))
            for owner, forecast_key, count, amount in result
        ]

    async def tally_by_month(self) -> Sequence[MonthlyBucket]:
        year = extract("year", DealRow.revenue_date)
        month = extract("month", DealRow.revenue_date)
        statement = select(
            year,
            month,
            DealRow.owner_user_id,
            DealRow.forecast_key,
            func.count(),
            func.coalesce(func.sum(DealRow.revenue_amount), 0),
        ).group_by(year, month, DealRow.owner_user_id, DealRow.forecast_key)
        result = await self._session.execute(statement)
        return [
            MonthlyBucket(
                int(y), int(m), UserId(owner), forecast_key, Tally(int(count), int(amount))
            )
            for y, m, owner, forecast_key, count, amount in result
        ]
