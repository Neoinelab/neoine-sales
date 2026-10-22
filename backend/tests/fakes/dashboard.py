"""DashboardTallyRepository Port의 InMemory 구현(Fake).

Deal 저장소(`FakeDealRepository`)가 `DealQuery`로 찾은 Deal을 묶어 건수와 `revenue_amount` 합을
낸다. 조건 판정은 Deal 목록과 같은 Fake 검색(`_found`)을 쓰므로 "집계 = 원장"이 구조로 보장되고,
SQL 구현과의 일치는 `tests/unit/repositories/test_dashboard_tally_contract.py`가 확인한다.
분기는 Fake가 `(month - 1) // 3 + 1`로 직접 계산한다(구현의 `quarter_of`를 베끼지 않는다).

domain/application 모듈은 호출 시점에 가져온다(구현이 없어도 FakeUnitOfWork를 쓰는 다른 테스트의
수집이 막히지 않게).
"""

from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.ports.deal_repository import DealQuery
    from app.domain.dashboard.quarter_closing import QuarterBucket
    from app.domain.forecast.summary import Tally


class FakeDashboardTallyRepository:
    def __init__(self, deals: Any) -> None:  # noqa: ANN401 - FakeDealRepository
        self._deals = deals

    async def tally_by_status(self, query: DealQuery) -> Mapping[str, Tally]:
        from app.domain.forecast.summary import Tally  # noqa: PLC0415

        counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for deal in self._deals._found(query):
            cell = counts[deal.sync.status_key]
            cell[0] += 1
            cell[1] += deal.details.revenue_amount.value
        return {key: Tally(count, amount) for key, (count, amount) in counts.items()}

    async def tally_by_quarter(self, query: DealQuery) -> Sequence[QuarterBucket]:
        from app.domain.dashboard.quarter_closing import QuarterBucket  # noqa: PLC0415
        from app.domain.forecast.summary import Tally  # noqa: PLC0415

        if query.year is None or query.quarter is not None or query.month is not None:
            msg = "tally_by_quarter는 연 단위 질의(year만, quarter·month 없음) 전용이다"
            raise ValueError(msg)
        counts: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
        for deal in self._deals._found(query):
            quarter = (deal.details.revenue_date.month - 1) // 3 + 1
            cell = counts[(quarter, deal.sync.forecast_key)]
            cell[0] += 1
            cell[1] += deal.details.revenue_amount.value
        return [
            QuarterBucket(quarter=quarter, forecast_key=key, tally=Tally(count, amount))
            for (quarter, key), (count, amount) in counts.items()
        ]
