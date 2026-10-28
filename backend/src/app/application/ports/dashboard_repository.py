from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.ports.deal_repository import DealQuery
    from app.domain.dashboard.quarter_closing import QuarterBucket
    from app.domain.forecast.summary import Tally


class DashboardTallyRepository(Protocol):
    """Deal 원장에서 바로 읽는 Dashboard 집계(읽기 전용). 조건은 Deal 목록과 같은 DealQuery."""

    async def tally_by_status(self, query: DealQuery) -> Mapping[str, Tally]:
        """query 조건의 Deal을 status_key별로 묶은 건수·revenue_amount 합(원 단위).

        Deal 없는 key는 빠진다. 페이지(offset·limit)·정렬은 무시한다.
        위험 필터가 있는데 risk_basis가 없으면 ValueError.
        """
        ...

    async def tally_by_quarter(self, query: DealQuery) -> Sequence[QuarterBucket]:
        """query 조건의 Deal을 (revenue_date 분기, forecast_key)로 묶은 건수·금액. Lost 포함.

        query.year가 없거나 quarters·month가 있으면 ValueError(연 단위 질의 전용).
        """
        ...
