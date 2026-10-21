"""ForecastTallyRepository Port의 InMemory 구현(Fake, P6 R1).

Deal 저장소(`FakeDealRepository`)의 Deal을 (담당자, Forecast key)로 묶어 건수와 `revenue_amount`
합을 낸다. 기간은 Expected Close(revenue_date)가 연 / 연+분기 / 연+월(양끝 포함)에 속하는지로
Fake가 직접 계산한다(구현의 `ForecastPeriod.date_range`를 베끼지 않는다). Lost도 그대로 묶는다
(제외는 도메인 규칙).

domain/application 모듈은 호출 시점에 가져온다(구현이 없어도 FakeUnitOfWork를 쓰는 다른 테스트의
수집이 막히지 않게).
"""

import calendar
from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.forecast_repository import ForecastCriteria, MonthlyBucket
    from app.domain.forecast.summary import ForecastBucket


def _bounds(year: int, quarter: int | None, month: int | None) -> tuple[date, date]:
    if month is not None:
        first = last = month
    elif quarter is not None:
        first, last = (quarter - 1) * 3 + 1, quarter * 3
    else:
        first, last = 1, 12
    return date(year, first, 1), date(year, last, calendar.monthrange(year, last)[1])


class FakeForecastTallyRepository:
    def __init__(self, deals: Any) -> None:  # noqa: ANN401 - FakeDealRepository
        self._deals = deals

    async def tally(self, criteria: ForecastCriteria) -> Sequence[ForecastBucket]:
        from app.domain.forecast.summary import ForecastBucket, Tally  # noqa: PLC0415

        period = criteria.period
        start, end = _bounds(period.year, period.quarter, period.month)
        counts: dict[tuple[Any, str], list[int]] = defaultdict(lambda: [0, 0])
        for deal in self._deals._items.values():
            details = deal.details
            if not start <= details.revenue_date <= end:
                continue
            if (
                criteria.owner_user_id is not None
                and details.owner_user_id != criteria.owner_user_id
            ):
                continue
            if criteria.vendor_id is not None and details.vendor_id != criteria.vendor_id:
                continue
            cell = counts[(details.owner_user_id, deal.sync.forecast_key)]
            cell[0] += 1
            cell[1] += details.revenue_amount.value
        return [
            ForecastBucket(owner_id=owner, forecast_key=key, tally=Tally(count, amount))
            for (owner, key), (count, amount) in counts.items()
        ]

    async def tally_by_month(self) -> Sequence[MonthlyBucket]:
        """모든 Deal을 (revenue 연, revenue 월, 담당자, Forecast key)로 묶는다(R2 스냅숏용)."""
        from app.application.ports.forecast_repository import MonthlyBucket  # noqa: PLC0415
        from app.domain.forecast.summary import Tally  # noqa: PLC0415

        counts: dict[tuple[int, int, Any, str], list[int]] = defaultdict(lambda: [0, 0])
        for deal in self._deals._items.values():
            details = deal.details
            day = details.revenue_date
            cell = counts[(day.year, day.month, details.owner_user_id, deal.sync.forecast_key)]
            cell[0] += 1
            cell[1] += details.revenue_amount.value
        return [
            MonthlyBucket(
                revenue_year=year,
                revenue_month=month,
                owner_id=owner,
                forecast_key=key,
                tally=Tally(count, amount),
            )
            for (year, month, owner, key), (count, amount) in counts.items()
        ]
