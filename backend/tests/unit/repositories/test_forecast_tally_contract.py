"""ForecastTallyRepository 계약: Fake와 SQL에 같은 기대값.

조건에 맞는 Deal을 (담당자, Forecast key)로 묶은 건수와 revenue_amount 합. 기간은 revenue_date
기준(연 / 연+분기 / 연+월, 양끝 포함), Lost도 묶음에 포함(제외는 도메인 규칙), owner·vendor 조건은
AND다. 합계는 같은 조건의 Deal 목록(원장) 건수와 같아야 한다.
"""

from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.deal.code import DealCode
from app.domain.forecast.period import ForecastPeriod
from tests.factories import date_after, later
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
    """Deal이 없으면 묶음이 없다"""
    # when: 조건에 맞는 Deal 없이 집계한다
    found = await _tally(forecast_case, _criteria())
    # then: 묶음이 없다
    assert found == {}


async def test_deals_are_grouped_by_owner_and_forecast_key(forecast_case: ForecastCase) -> None:
    """Deal을 담당자·Forecast key로 묶어 건수와 금액을 더한다"""
    # given: KIM·LEE의 pipeline·commit Deal
    await forecast_case.add_deal(owner=KIM, forecast="pipeline", amount=100)
    await forecast_case.add_deal(owner=KIM, forecast="pipeline", amount=40)
    await forecast_case.add_deal(owner=KIM, forecast="commit", amount=7)
    await forecast_case.add_deal(owner=LEE, forecast="pipeline", amount=5)

    # when: 집계한다
    found = await _tally(forecast_case, _criteria())

    # then: (담당자, key)별 건수·금액이다
    assert found == {
        (KIM, "pipeline"): (2, 140),
        (KIM, "commit"): (1, 7),
        (LEE, "pipeline"): (1, 5),
    }


async def test_lost_and_won_deals_are_grouped_like_any_other_key(
    forecast_case: ForecastCase,
) -> None:
    """Lost·Won Deal도 다른 key처럼 묶는다"""
    # given: Lost·Won Deal 하나씩
    await forecast_case.add_deal(forecast="lost", amount=9)
    await forecast_case.add_deal(forecast="won", amount=11)

    # when: 집계한다
    found = await _tally(forecast_case, _criteria())

    # then: lost·won 묶음이 각각 있다
    assert found == {(OWNER_ID, "lost"): (1, 9), (OWNER_ID, "won"): (1, 11)}


async def test_amounts_beyond_32_bits_are_summed_exactly(forecast_case: ForecastCase) -> None:
    """32비트를 넘는 금액도 정확히 더한다

    테스트 코드: FC-013
    """
    # given: 같은 담당자·코드의 큰 금액 Deal 두 건
    big = 2**40
    await forecast_case.add_deal(amount=big)
    await forecast_case.add_deal(amount=big + 1)

    # when: 집계한다
    found = await _tally(forecast_case, _criteria())

    # then: 금액 합이 정확하다
    assert found == {(OWNER_ID, "pipeline"): (2, 2 * big + 1)}


async def test_a_year_alone_includes_january_first_and_december_31(
    forecast_case: ForecastCase,
) -> None:
    """연도만 주면 그 해 1/1과 12/31을 포함하고 이웃 해는 뺀다

    테스트 코드: FC-007
    """
    # given: 전년 12/31, 1/1, 12/31, 다음 해 1/1의 Deal
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await forecast_case.add_deal(day=day, amount=1)

    # when: 2026년으로 집계한다
    found = await _tally(forecast_case, _criteria(year=2026))

    # then: 2026년 두 건만 들어온다
    assert found == {(OWNER_ID, "pipeline"): (2, 2)}


async def test_quarter_bounds_are_inclusive_and_exclude_neighbours(
    forecast_case: ForecastCase,
) -> None:
    """분기 양끝은 포함하고 이웃 분기는 뺀다

    테스트 코드: FC-007
    """
    # given: 9/30, 10/1, 12/31, 다음 해 1/1의 Deal
    for day in (date(2026, 9, 30), date(2026, 10, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await forecast_case.add_deal(day=day, amount=1)

    # when: 2026 Q4와 2027 Q1로 각각 집계한다
    q4 = await _tally(forecast_case, _criteria(quarter=4))
    q1_next = await _tally(forecast_case, _criteria(year=2027, quarter=1))

    # then: Q4는 10/1·12/31, 다음 해 Q1은 1/1만이다
    assert q4 == {(OWNER_ID, "pipeline"): (2, 2)}
    assert q1_next == {(OWNER_ID, "pipeline"): (1, 1)}


async def test_month_bounds_are_inclusive_including_a_leap_february(
    forecast_case: ForecastCase,
) -> None:
    """월 양끝은 포함하고 윤년 2월은 29일까지다

    테스트 코드: FC-007
    """
    # given: 1/31, 2/1, 2/29, 3/1의 Deal
    for day in (date(2028, 1, 31), date(2028, 2, 1), date(2028, 2, 29), date(2028, 3, 1)):
        await forecast_case.add_deal(day=day, amount=1)

    # when: 2028년 2월로 집계한다
    found = await _tally(forecast_case, _criteria(year=2028, month=2))

    # then: 2/1과 2/29만 들어온다
    assert found == {(OWNER_ID, "pipeline"): (2, 2)}


async def test_owner_condition_limits_to_that_owner(forecast_case: ForecastCase) -> None:
    """담당자 조건은 그 담당자 Deal만 센다

    테스트 코드: FC-008
    """
    # given: KIM·LEE의 Deal
    await forecast_case.add_deal(owner=KIM, amount=3)
    await forecast_case.add_deal(owner=LEE, amount=4)

    # when: LEE 조건으로 집계한다
    found = await _tally(forecast_case, _criteria(owner_user_id=LEE))

    # then: LEE 묶음뿐이다
    assert found == {(LEE, "pipeline"): (1, 4)}


async def test_vendor_condition_limits_to_that_vendor(forecast_case: ForecastCase) -> None:
    """Vendor 조건은 그 Vendor의 Deal만 센다

    테스트 코드: FC-008
    """
    # given: SAP·Oracle·Vendor 없는 Deal
    sap = await forecast_case.deals.new_vendor("SAP")
    oracle = await forecast_case.deals.new_vendor("Oracle")
    await forecast_case.add_deal(amount=1, vendor_id=sap.id)
    await forecast_case.add_deal(amount=2, vendor_id=oracle.id)
    await forecast_case.add_deal(amount=4)

    # when: SAP 조건으로 집계한다
    found = await _tally(forecast_case, _criteria(vendor_id=sap.id))

    # then: SAP Deal만 센다
    assert found == {(OWNER_ID, "pipeline"): (1, 1)}


async def test_no_vendor_condition_includes_deals_without_a_vendor(
    forecast_case: ForecastCase,
) -> None:
    """Vendor 조건이 없으면 Vendor 없는 Deal도 센다

    테스트 코드: FC-008
    """
    # given: SAP Deal과 Vendor 없는 Deal
    sap = await forecast_case.deals.new_vendor("SAP")
    await forecast_case.add_deal(amount=1, vendor_id=sap.id)
    await forecast_case.add_deal(amount=4)

    # when: Vendor 조건 없이 집계한다
    found = await _tally(forecast_case, _criteria())

    # then: 두 Deal을 모두 센다
    assert found == {(OWNER_ID, "pipeline"): (2, 5)}


async def test_a_resigned_owner_still_appears(forecast_case: ForecastCase) -> None:
    """퇴사한 담당자의 Deal도 묶음에 나온다"""
    # given: KIM의 Deal 후 KIM 퇴사
    await forecast_case.add_deal(owner=KIM, amount=3)
    await forecast_case.deals.resign(KIM, later(10_000))

    # when: 집계한다
    found = await _tally(forecast_case, _criteria())

    # then: KIM 묶음이 그대로 있다
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
    """같은 조건의 집계 합계는 Deal 목록(원장) 합계와 같다

    테스트 코드: FC-011
    """
    # given: 여러 담당자·코드·날짜의 Deal(Lost 포함)
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

    # when: 집계와 같은 조건의 Deal 목록을 읽는다
    buckets = list(await forecast_case.forecast.tally(criteria))
    ledger = await forecast_case.deals.deals.search(replace(criteria.to_deal_query(), limit=200))

    # then: 건수·금액 합이 같다
    assert sum(b.tally.count for b in buckets) == len(ledger)
    assert sum(b.tally.amount for b in buckets) == sum(
        item.deal.details.revenue_amount.value for item in ledger
    )


async def test_forecast_summary_is_unchanged_by_the_risk_fields(
    forecast_case: ForecastCase,
) -> None:
    """경고 상태(기한초과·미업데이트)는 Forecast 집계를 바꾸지 않는다

    테스트 코드: FC-012
    """
    # given: Due가 지난 Deal, 오래된 미업데이트 Deal, Won Deal
    overdue_code = await forecast_case.add_deal(forecast="pipeline", amount=100)
    stale_code = await forecast_case.add_deal(forecast="commit", amount=7)
    await forecast_case.add_deal(forecast="won", amount=11)
    deal = await forecast_case.deals.deals.get(DealCode(overdue_code))
    await forecast_case.deals.add_action(deal, acted_on=date_after(0), due_date=date(2026, 1, 2))

    # when: 집계한다
    found = await _tally(forecast_case, _criteria())

    # then: 두 Deal은 서로 다르고, 경고와 무관하게 건수·금액 그대로다
    assert stale_code != overdue_code
    assert found == {
        (OWNER_ID, "pipeline"): (1, 100),
        (OWNER_ID, "commit"): (1, 7),
        (OWNER_ID, "won"): (1, 11),
    }


async def test_separated_quarters_are_summed_without_the_quarter_between_them(
    forecast_case: ForecastCase,
) -> None:
    """떨어진 분기는 사이 분기를 빼고 합친다"""
    # given: Q1~Q4 경계 날짜의 Deal
    for day, amount in (
        (date(2026, 3, 31), 1),
        (date(2026, 4, 1), 100),
        (date(2026, 6, 30), 100),
        (date(2026, 7, 1), 10),
        (date(2026, 9, 30), 20),
        (date(2026, 10, 1), 1000),
    ):
        await forecast_case.add_deal(day=day, amount=amount)

    # when: Q1·Q3로 집계한다
    found = await _tally(forecast_case, _criteria(quarters=frozenset({1, 3})))

    # then: Q1·Q3의 Deal만 합쳐진다
    assert found == {(OWNER_ID, "pipeline"): (3, 31)}


@pytest.mark.parametrize("with_owner", [False, True], ids=["vendor", "month-owner-vendor"])
async def test_tally_totals_equal_the_deal_list_ledger_with_a_vendor_condition(
    forecast_case: ForecastCase, with_owner: bool
) -> None:
    """Vendor 조건(월·담당자와 함께인 경우 포함)에서도 집계 합계는 Deal 목록 합계와 같다.

    테스트 코드: FC-011
    """
    # given: SAP·Oracle·IBM Deal을 KIM·LEE가 11월과 12월에 가진 상태
    sap = await forecast_case.deals.new_vendor("SAP")
    oracle = await forecast_case.deals.new_vendor("Oracle")
    ibm = await forecast_case.deals.new_vendor("IBM")
    vendors = [sap.id, oracle.id, ibm.id, sap.id]
    for number, vendor_id in enumerate(vendors):
        await forecast_case.add_deal(
            owner=KIM if number % 2 == 0 else LEE,
            forecast="commit" if number != 2 else "lost",
            amount=10 + number,
            day=date(2026, 11, 1 + number) if number < 3 else date(2026, 12, 1),
            vendor_id=vendor_id,
        )
    criteria = (
        _criteria(month=11, owner_user_id=KIM, vendor_id=sap.id)
        if with_owner
        else _criteria(vendor_id=sap.id)
    )
    # when: 집계와 같은 조건의 Deal 목록을 읽는다
    buckets = list(await forecast_case.forecast.tally(criteria))
    ledger = await forecast_case.deals.deals.search(replace(criteria.to_deal_query(), limit=200))
    # then: Lost까지 포함한 건수·금액 합이 같다
    assert sum(b.tally.count for b in buckets) == len(ledger) > 0
    assert sum(b.tally.amount for b in buckets) == sum(
        item.deal.details.revenue_amount.value for item in ledger
    )
