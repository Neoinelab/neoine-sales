"""Forecast key 집합 조회가 Dashboard의 outcome 집계와 같은 Deal을 고른다 (Fake·SQL 공통).

Drill-down은 Dashboard 응답의 Forecast 열(key)로 `forecast_keys`를 만든다. admin이 추가한 Open
코드를 포함해 `forecast_keys=<Open 코드 key 전부>`는 `forecast_outcome=OPEN`과, `<Lost 아닌 key
전부>`는 `NOT_LOST`와 같은 건수여야 한다. key 목록은 코드 저장소에서 읽는다(구현의
`ForecastOutcomeFilter`를 베끼지 않는다).
"""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from tests.factories import NOW, later, make_deal
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


def _code(number: int) -> str:
    return f"20261016-A{number:03d}"


async def _count(case: DealCase, **criteria: object) -> int:
    return int(await case.deals.count(DealQuery(**criteria)))  # type: ignore[arg-type]


async def _keys(case: DealCase, wanted: set[ForecastOutcome]) -> frozenset[str]:
    codes = await case.codes.list(CodeKind.FORECAST)
    return frozenset(c.key.value for c in codes if c.outcome in wanted)


async def _seed(case: DealCase) -> None:
    await case.codes.add(
        Code.create(
            entity_id=CodeId(new_id()),
            kind=CodeKind.FORECAST,
            name="Verbal",
            key=CodeKey("verbal"),
            order=99,
            probability_hint=None,
            now=NOW,
        )
    )
    placed = (
        ("pipeline", date(2026, 2, 1)),
        ("commit", date(2026, 5, 1)),
        ("verbal", date(2026, 5, 20)),
        ("verbal", date(2026, 11, 3)),
        ("won", date(2026, 5, 2)),
        ("lost", date(2026, 5, 3)),
    )
    for number, (forecast, day) in enumerate(placed, start=1):
        await case.add(
            make_deal(
                later(number),
                code=_code(number),
                forecast_key=forecast,
                revenue_date=day,
                status_key="contract_completed" if forecast == "won" else "prospecting",
            )
        )


async def test_the_open_key_set_counts_the_same_as_the_open_outcome(deal_case: DealCase) -> None:
    await _seed(deal_case)
    open_keys = await _keys(deal_case, {ForecastOutcome.OPEN})

    assert "verbal" in open_keys
    by_keys = await _count(deal_case, forecast_keys=open_keys)
    assert by_keys == await _count(deal_case, forecast_outcome=ForecastOutcomeFilter.OPEN)
    assert by_keys == 4


async def test_the_not_lost_key_set_counts_the_same_as_the_not_lost_outcome(
    deal_case: DealCase,
) -> None:
    await _seed(deal_case)
    keys = await _keys(deal_case, {ForecastOutcome.OPEN, ForecastOutcome.WON})

    by_keys = await _count(deal_case, forecast_keys=keys)
    assert by_keys == await _count(deal_case, forecast_outcome=ForecastOutcomeFilter.NOT_LOST)
    assert by_keys == 5


async def test_the_equality_holds_with_year_and_quarter_conditions(deal_case: DealCase) -> None:
    await _seed(deal_case)
    open_keys = await _keys(deal_case, {ForecastOutcome.OPEN})
    not_lost = await _keys(deal_case, {ForecastOutcome.OPEN, ForecastOutcome.WON})

    scope = {"year": 2026, "quarters": frozenset({2})}
    assert await _count(deal_case, forecast_keys=open_keys, **scope) == await _count(
        deal_case, forecast_outcome=ForecastOutcomeFilter.OPEN, **scope
    )
    assert await _count(deal_case, forecast_keys=not_lost, **scope) == await _count(
        deal_case, forecast_outcome=ForecastOutcomeFilter.NOT_LOST, **scope
    )
    assert await _count(deal_case, forecast_keys=open_keys, **scope) == 2
