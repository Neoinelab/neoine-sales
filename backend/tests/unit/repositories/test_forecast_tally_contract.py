"""ForecastTallyRepository 계약(P6 R1 AC-3·4·6·7): Fake와 SQL에 같은 기대값.

조건에 맞는 Deal을 (담당자, Forecast key)로 묶은 건수와 revenue_amount 합. 기간은 revenue_date
기준(연 / 연+분기 / 연+월, 양끝 포함), Lost도 묶음에 포함(제외는 도메인 규칙), owner·vendor 조건은
AND다. 합계는 같은 조건의 Deal 목록(원장) 건수와 같아야 한다(검수 4).
"""

from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.deal.code import DealCode
from app.domain.forecast.period import ForecastPeriod
from tests.factories import later
from tests.support.user_ids import OWNER_ID, uid

if TYPE_CHECKING:
    from app.domain.forecast.summary import ForecastBucket
    from tests.unit.repositories.forecast_case import ForecastCase

KIM = uid("tally-kim")
LEE = uid("tally-lee")


def _criteria(
    year: int = 2026,
    quarter: int | None = None,
    month: int | None = None,
    quarters: frozenset[int] | None = None,
    **rest: object,
) -> ForecastCriteria:
    period = ForecastPeriod(
        year=year, quarters=quarters if quarter is None else frozenset({quarter}), month=month
    )
    return ForecastCriteria(period=period, **rest)  # type: ignore[arg-type]


def _cells(
    buckets: list[ForecastBucket] | tuple[ForecastBucket, ...],
) -> dict[tuple[int, str], tuple[int, int]]:
    return {(b.owner_id, b.forecast_key): (b.tally.count, b.tally.amount) for b in buckets}


async def _tally(
    case: ForecastCase, criteria: ForecastCriteria
) -> dict[tuple[int, str], tuple[int, int]]:
    return _cells(list(await case.forecast.tally(criteria)))


async def test_no_deals_gives_no_buckets(forecast_case: ForecastCase) -> None:
    assert await _tally(forecast_case, _criteria()) == {}


async def test_deals_are_grouped_by_owner_and_forecast_key(forecast_case: ForecastCase) -> None:
    await forecast_case.add_deal(owner=KIM, forecast="pipeline", amount=100)
    await forecast_case.add_deal(owner=KIM, forecast="pipeline", amount=40)
    await forecast_case.add_deal(owner=KIM, forecast="commit", amount=7)
    await forecast_case.add_deal(owner=LEE, forecast="pipeline", amount=5)

    found = await _tally(forecast_case, _criteria())

    assert found == {
        (KIM, "pipeline"): (2, 140),
        (KIM, "commit"): (1, 7),
        (LEE, "pipeline"): (1, 5),
    }


async def test_lost_and_won_deals_are_grouped_like_any_other_key(
    forecast_case: ForecastCase,
) -> None:
    await forecast_case.add_deal(forecast="lost", amount=9)
    await forecast_case.add_deal(forecast="won", amount=11)

    found = await _tally(forecast_case, _criteria())

    assert found == {(OWNER_ID, "lost"): (1, 9), (OWNER_ID, "won"): (1, 11)}


async def test_amounts_beyond_32_bits_are_summed_exactly(forecast_case: ForecastCase) -> None:
    big = 2**40
    await forecast_case.add_deal(amount=big)
    await forecast_case.add_deal(amount=big + 1)

    found = await _tally(forecast_case, _criteria())

    assert found == {(OWNER_ID, "pipeline"): (2, 2 * big + 1)}


async def test_a_year_alone_includes_january_first_and_december_31(
    forecast_case: ForecastCase,
) -> None:
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await forecast_case.add_deal(day=day, amount=1)

    found = await _tally(forecast_case, _criteria(year=2026))

    assert found == {(OWNER_ID, "pipeline"): (2, 2)}


async def test_quarter_bounds_are_inclusive_and_exclude_neighbours(
    forecast_case: ForecastCase,
) -> None:
    for day in (date(2026, 9, 30), date(2026, 10, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await forecast_case.add_deal(day=day, amount=1)

    q4 = await _tally(forecast_case, _criteria(quarter=4))
    q1_next = await _tally(forecast_case, _criteria(year=2027, quarter=1))

    assert q4 == {(OWNER_ID, "pipeline"): (2, 2)}
    assert q1_next == {(OWNER_ID, "pipeline"): (1, 1)}


async def test_month_bounds_are_inclusive_including_a_leap_february(
    forecast_case: ForecastCase,
) -> None:
    for day in (date(2028, 1, 31), date(2028, 2, 1), date(2028, 2, 29), date(2028, 3, 1)):
        await forecast_case.add_deal(day=day, amount=1)

    found = await _tally(forecast_case, _criteria(year=2028, month=2))

    assert found == {(OWNER_ID, "pipeline"): (2, 2)}


async def test_owner_condition_limits_to_that_owner(forecast_case: ForecastCase) -> None:
    await forecast_case.add_deal(owner=KIM, amount=3)
    await forecast_case.add_deal(owner=LEE, amount=4)

    found = await _tally(forecast_case, _criteria(owner_user_id=LEE))

    assert found == {(LEE, "pipeline"): (1, 4)}


async def test_vendor_condition_limits_to_that_vendor(forecast_case: ForecastCase) -> None:
    sap = await forecast_case.deals.new_vendor("SAP")
    oracle = await forecast_case.deals.new_vendor("Oracle")
    await forecast_case.add_deal(amount=1, vendor_id=sap.id)
    await forecast_case.add_deal(amount=2, vendor_id=oracle.id)
    await forecast_case.add_deal(amount=4)

    found = await _tally(forecast_case, _criteria(vendor_id=sap.id))

    assert found == {(OWNER_ID, "pipeline"): (1, 1)}


async def test_no_vendor_condition_includes_deals_without_a_vendor(
    forecast_case: ForecastCase,
) -> None:
    sap = await forecast_case.deals.new_vendor("SAP")
    await forecast_case.add_deal(amount=1, vendor_id=sap.id)
    await forecast_case.add_deal(amount=4)

    found = await _tally(forecast_case, _criteria())

    assert found == {(OWNER_ID, "pipeline"): (2, 5)}


async def test_a_resigned_owner_still_appears(forecast_case: ForecastCase) -> None:
    await forecast_case.add_deal(owner=KIM, amount=3)
    await forecast_case.deals.resign(KIM, later(10_000))

    found = await _tally(forecast_case, _criteria())

    assert found == {(KIM, "pipeline"): (1, 3)}


@pytest.mark.parametrize(
    "criteria",
    [
        _criteria(),
        _criteria(quarter=4),
        _criteria(month=11),
        _criteria(month=12),
        _criteria(owner_user_id=KIM),
        _criteria(quarter=4, owner_user_id=LEE),
    ],
    ids=["year", "quarter", "month", "month-end", "owner", "quarter-owner"],
)
async def test_tally_totals_equal_the_deal_list_ledger_for_the_same_condition(
    forecast_case: ForecastCase, criteria: ForecastCriteria
) -> None:
    days = [
        date(2026, 3, 1),
        date(2026, 11, 1),
        date(2026, 11, 30),
        date(2026, 12, 31),
        date(2027, 1, 1),
    ]
    for number, day in enumerate(days):
        await forecast_case.add_deal(
            owner=KIM if number % 2 == 0 else LEE,
            forecast="commit" if number % 3 else "lost",
            amount=10 + number,
            day=day,
        )

    buckets = list(await forecast_case.forecast.tally(criteria))
    ledger = await forecast_case.deals.deals.search(replace(criteria.to_deal_query(), limit=200))

    assert sum(b.tally.count for b in buckets) == len(ledger)
    assert sum(b.tally.amount for b in buckets) == sum(
        item.deal.details.revenue_amount.value for item in ledger
    )


async def test_forecast_summary_is_unchanged_by_the_risk_fields(
    forecast_case: ForecastCase,
) -> None:
    """Deal 목록의 기한초과·미업데이트 필터 추가가 Forecast 집계를 바꾸지 않는다(AC-11).

    등록 시각이 오래되어 미업데이트이고 Due가 지난 Deal도, 종결 Deal도 모두 센다.
    """
    overdue_code = await forecast_case.add_deal(forecast="pipeline", amount=100)
    stale_code = await forecast_case.add_deal(forecast="commit", amount=7)
    await forecast_case.add_deal(forecast="won", amount=11)
    deal = await forecast_case.deals.deals.get(DealCode(overdue_code))
    await forecast_case.deals.add_action(deal, acted_at=later(5), due_date=date(2026, 1, 2))
    assert stale_code != overdue_code

    found = await _tally(forecast_case, _criteria())

    assert found == {
        (OWNER_ID, "pipeline"): (1, 100),
        (OWNER_ID, "commit"): (1, 7),
        (OWNER_ID, "won"): (1, 11),
    }


async def test_separated_quarters_are_summed_without_the_quarter_between_them(
    forecast_case: ForecastCase,
) -> None:
    for day, amount in (
        (date(2026, 3, 31), 1),
        (date(2026, 4, 1), 100),
        (date(2026, 6, 30), 100),
        (date(2026, 7, 1), 10),
        (date(2026, 9, 30), 20),
        (date(2026, 10, 1), 1000),
    ):
        await forecast_case.add_deal(day=day, amount=amount)

    found = await _tally(forecast_case, _criteria(quarters=frozenset({1, 3})))

    assert found == {(OWNER_ID, "pipeline"): (3, 31)}
