"""ForecastTallyRepository.tally_by_month 계약: Fake와 SQL에 같은 기대값.

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
    """Deal이 없으면 월별 묶음이 없다"""
    # when: 월별 집계를 읽는다
    found = await _found(forecast_case)
    # then: 묶음이 없다
    assert found == {}


async def test_deals_are_grouped_by_revenue_month_owner_and_forecast(
    forecast_case: ForecastCase,
) -> None:
    """Deal을 Expected Close 연·월·담당자·key로 묶는다"""
    # given: 11·12월, 두 코드, 두 담당자의 Deal
    await forecast_case.add_deal(day=date(2026, 11, 1), amount=100)
    await forecast_case.add_deal(day=date(2026, 11, 30), amount=40)
    await forecast_case.add_deal(day=date(2026, 12, 1), amount=7)
    await forecast_case.add_deal(day=date(2026, 11, 15), forecast="commit", amount=5)
    await forecast_case.add_deal(day=date(2026, 11, 15), owner=KIM, amount=9)

    # when: 월별로 집계한다
    found = await _found(forecast_case)
    # then: 연·월·담당자·key별 건수·금액이다
    assert found == {
        (2026, 11, OWNER_ID, "pipeline"): (2, 140),
        (2026, 12, OWNER_ID, "pipeline"): (1, 7),
        (2026, 11, OWNER_ID, "commit"): (1, 5),
        (2026, 11, KIM, "pipeline"): (1, 9),
    }


async def test_the_same_month_of_different_years_is_not_merged(
    forecast_case: ForecastCase,
) -> None:
    """다른 해의 같은 달은 합치지 않는다"""
    # given: 2025-03과 2026-03의 Deal
    await forecast_case.add_deal(day=date(2025, 3, 15), amount=1)
    await forecast_case.add_deal(day=date(2026, 3, 15), amount=2)

    # when: 월별로 집계한다
    found = await _found(forecast_case)
    # then: 연도별로 따로 묶인다
    assert found == {
        (2025, 3, OWNER_ID, "pipeline"): (1, 1),
        (2026, 3, OWNER_ID, "pipeline"): (1, 2),
    }


async def test_lost_and_won_deals_are_included(forecast_case: ForecastCase) -> None:
    """Lost·Won Deal도 포함한다"""
    # given: Lost·Won Deal 하나씩
    await forecast_case.add_deal(forecast="lost", amount=9)
    await forecast_case.add_deal(forecast="won", amount=11)

    # when: 월별로 집계한다
    found = await _found(forecast_case)
    # then: lost·won 묶음이 있다
    assert found == {
        (2026, 11, OWNER_ID, "lost"): (1, 9),
        (2026, 11, OWNER_ID, "won"): (1, 11),
    }


async def test_monthly_amounts_beyond_32_bits_are_summed_exactly(
    forecast_case: ForecastCase,
) -> None:
    """월별 묶음도 32비트를 넘는 금액을 정확히 더한다

    테스트 코드: FC-013
    """
    # given: 같은 담당자·코드의 큰 금액 Deal 두 건
    big = 2**40
    await forecast_case.add_deal(amount=big)
    await forecast_case.add_deal(amount=big + 1)

    # when: 월별로 집계한다
    found = await _found(forecast_case)
    # then: 금액 합이 정확하다
    assert found == {(2026, 11, OWNER_ID, "pipeline"): (2, 2 * big + 1)}
