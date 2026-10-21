"""ForecastTallyRepository.tally_by_month 계약(P6 R2 AC-13): Fake와 SQL에 같은 기대값.

스냅숏의 원천이다. 모든 Deal을 (revenue 연, revenue 월, 담당자, Forecast key)로 묶은 건수와
revenue_amount 합. 기간 제한이 없고 Lost도 포함한다(제외는 표시 규칙).
"""

from datetime import date
from typing import TYPE_CHECKING

from tests.support.user_ids import OWNER_ID, uid

if TYPE_CHECKING:
    from tests.unit.repositories.forecast_case import ForecastCase

KIM = uid("by-month-kim")


async def _found(case: ForecastCase) -> dict[tuple[int, int, int, str], tuple[int, int]]:
    return {
        (b.revenue_year, b.revenue_month, b.owner_id, b.forecast_key): (
            b.tally.count,
            b.tally.amount,
        )
        for b in await case.forecast.tally_by_month()
    }


async def test_no_deals_gives_no_monthly_buckets(forecast_case: ForecastCase) -> None:
    assert await _found(forecast_case) == {}


async def test_deals_are_grouped_by_revenue_month_owner_and_forecast(
    forecast_case: ForecastCase,
) -> None:
    await forecast_case.add_deal(day=date(2026, 11, 1), amount=100)
    await forecast_case.add_deal(day=date(2026, 11, 30), amount=40)
    await forecast_case.add_deal(day=date(2026, 12, 1), amount=7)
    await forecast_case.add_deal(day=date(2026, 11, 15), forecast="commit", amount=5)
    await forecast_case.add_deal(day=date(2026, 11, 15), owner=KIM, amount=9)

    assert await _found(forecast_case) == {
        (2026, 11, OWNER_ID, "pipeline"): (2, 140),
        (2026, 12, OWNER_ID, "pipeline"): (1, 7),
        (2026, 11, OWNER_ID, "commit"): (1, 5),
        (2026, 11, KIM, "pipeline"): (1, 9),
    }


async def test_the_same_month_of_different_years_is_not_merged(
    forecast_case: ForecastCase,
) -> None:
    await forecast_case.add_deal(day=date(2025, 3, 15), amount=1)
    await forecast_case.add_deal(day=date(2026, 3, 15), amount=2)

    assert await _found(forecast_case) == {
        (2025, 3, OWNER_ID, "pipeline"): (1, 1),
        (2026, 3, OWNER_ID, "pipeline"): (1, 2),
    }


async def test_lost_and_won_deals_are_included(forecast_case: ForecastCase) -> None:
    await forecast_case.add_deal(forecast="lost", amount=9)
    await forecast_case.add_deal(forecast="won", amount=11)

    assert await _found(forecast_case) == {
        (2026, 11, OWNER_ID, "lost"): (1, 9),
        (2026, 11, OWNER_ID, "won"): (1, 11),
    }


async def test_monthly_amounts_beyond_32_bits_are_summed_exactly(
    forecast_case: ForecastCase,
) -> None:
    big = 2**40
    await forecast_case.add_deal(amount=big)
    await forecast_case.add_deal(amount=big + 1)

    assert await _found(forecast_case) == {(2026, 11, OWNER_ID, "pipeline"): (2, 2 * big + 1)}
