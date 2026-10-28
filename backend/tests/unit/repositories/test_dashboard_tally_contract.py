"""DashboardTallyRepository 계약 (Dashboard AC-4·5·18): Fake와 SQL에 같은 기대값.

- tally_by_status: DealQuery 조건의 Deal을 status_key별 (건수, revenue_amount 합)으로 묶는다.
  Deal 없는
  key는 빠지고, 페이지·정렬은 무시하며, 위험 필터가 있는데 risk_basis가 없으면 ValueError다.
- tally_by_quarter: 연 단위 질의 전용. (revenue_date 분기, Forecast key)로 묶고 Lost도 포함한다.
- 두 집계 모두 같은 조건의 Deal 목록(원장) 건수·금액과 같아야 한다.
"""

from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.forecast.summary import Tally
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.dashboard.quarter_closing import QuarterBucket
    from tests.unit.repositories.dashboard_case import DashboardCase

KIM = uid("dash-kim")
LEE = uid("dash-lee")


def _quarters(
    buckets: list[QuarterBucket] | tuple[QuarterBucket, ...],
) -> dict[tuple[int, str], Tally]:
    return {(b.quarter, b.forecast_key): b.tally for b in buckets}


async def _by_status(case: DashboardCase, **criteria: object) -> dict[str, Tally]:
    return dict(await case.dashboard.tally_by_status(DealQuery(**criteria)))  # type: ignore[arg-type]


async def _by_quarter(case: DashboardCase, **criteria: object) -> dict[tuple[int, str], Tally]:
    buckets = await case.dashboard.tally_by_quarter(DealQuery(**criteria))  # type: ignore[arg-type]
    return _quarters(list(buckets))


# ---- tally_by_status ----


async def test_no_deals_gives_no_status_entries(dashboard_case: DashboardCase) -> None:
    assert await _by_status(dashboard_case, year=2026) == {}


async def test_deals_are_grouped_by_status_key_with_count_and_amount(
    dashboard_case: DashboardCase,
) -> None:
    await dashboard_case.add_deal(status="prospecting", amount=100)
    await dashboard_case.add_deal(status="prospecting", amount=40)
    await dashboard_case.add_deal(status="poc_completed", amount=7)

    found = await _by_status(dashboard_case, year=2026)

    assert found == {"prospecting": Tally(2, 140), "poc_completed": Tally(1, 7)}


async def test_status_keys_without_deals_are_absent(dashboard_case: DashboardCase) -> None:
    await dashboard_case.add_deal(status="introduction", amount=1)

    found = await _by_status(dashboard_case, year=2026)

    assert set(found) == {"introduction"}


async def test_amounts_beyond_32_bits_are_summed_exactly_by_status(
    dashboard_case: DashboardCase,
) -> None:
    big = 2**40
    await dashboard_case.add_deal(amount=big)
    await dashboard_case.add_deal(amount=big + 1)

    assert await _by_status(dashboard_case, year=2026) == {"prospecting": Tally(2, 2 * big + 1)}


async def test_status_tally_with_not_lost_filter_drops_only_lost_deals(
    dashboard_case: DashboardCase,
) -> None:
    await dashboard_case.add_deal(forecast="pipeline", amount=1)
    await dashboard_case.add_deal(forecast="commit", amount=2, status="price_negotiation")
    await dashboard_case.add_deal(forecast="won", amount=4)
    await dashboard_case.add_deal(forecast="lost", amount=8, status="price_negotiation")

    found = await _by_status(
        dashboard_case, year=2026, forecast_outcome=ForecastOutcomeFilter.NOT_LOST
    )

    assert found == {
        "prospecting": Tally(1, 1),
        "price_negotiation": Tally(1, 2),
        "contract_completed": Tally(1, 4),
    }


async def test_status_tally_period_bounds_are_inclusive(dashboard_case: DashboardCase) -> None:
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await dashboard_case.add_deal(day=day, amount=1)

    year = await _by_status(dashboard_case, year=2026)
    q4 = await _by_status(dashboard_case, year=2026, quarters=frozenset({4}))
    jan = await _by_status(dashboard_case, year=2027, month=1)

    assert year == {"prospecting": Tally(2, 2)}
    assert q4 == {"prospecting": Tally(1, 1)}
    assert jan == {"prospecting": Tally(1, 1)}


async def test_status_tally_owner_and_vendor_conditions_are_anded(
    dashboard_case: DashboardCase,
) -> None:
    sap = await dashboard_case.deals.new_vendor("SAP")
    await dashboard_case.add_deal(owner=KIM, vendor_id=sap.id, amount=1)
    await dashboard_case.add_deal(owner=KIM, amount=2)
    await dashboard_case.add_deal(owner=LEE, vendor_id=sap.id, amount=4)

    both = await _by_status(dashboard_case, year=2026, owner_user_id=KIM, vendor_id=sap.id)
    owner = await _by_status(dashboard_case, year=2026, owner_user_id=KIM)

    assert both == {"prospecting": Tally(1, 1)}
    assert owner == {"prospecting": Tally(2, 3)}


async def test_status_tally_ignores_page_and_sort(dashboard_case: DashboardCase) -> None:
    for number in range(5):
        await dashboard_case.add_deal(amount=10 + number)

    found = await dashboard_case.dashboard.tally_by_status(DealQuery(year=2026, offset=3, limit=1))

    assert dict(found) == {"prospecting": Tally(5, 60)}


async def test_status_tally_with_a_risk_filter_needs_a_risk_basis(
    dashboard_case: DashboardCase,
) -> None:
    await dashboard_case.add_deal()

    with pytest.raises(ValueError, match=r"."):
        await dashboard_case.dashboard.tally_by_status(DealQuery(overdue=True))


async def test_status_tally_with_a_risk_filter_and_basis_counts_matching_deals(
    dashboard_case: DashboardCase,
) -> None:
    from app.domain.deal.risk import RiskBasis  # noqa: PLC0415

    await dashboard_case.add_deal(amount=3)
    basis = RiskBasis(today=date(2026, 11, 30), stale_days=14)  # 등록 시각이 오래 지나 stale

    found = await dashboard_case.dashboard.tally_by_status(DealQuery(stale=True, risk_basis=basis))

    assert dict(found) == {"prospecting": Tally(1, 3)}


# ---- tally_by_quarter ----


async def test_no_deals_gives_no_quarter_buckets(dashboard_case: DashboardCase) -> None:
    assert await _by_quarter(dashboard_case, year=2026) == {}


async def test_deals_are_grouped_by_quarter_and_forecast_key(
    dashboard_case: DashboardCase,
) -> None:
    await dashboard_case.add_deal(forecast="pipeline", amount=100, day=date(2026, 2, 1))
    await dashboard_case.add_deal(forecast="pipeline", amount=40, day=date(2026, 3, 31))
    await dashboard_case.add_deal(forecast="commit", amount=7, day=date(2026, 4, 1))
    await dashboard_case.add_deal(forecast="won", amount=5, day=date(2026, 12, 31))

    found = await _by_quarter(dashboard_case, year=2026)

    assert found == {
        (1, "pipeline"): Tally(2, 140),
        (2, "commit"): Tally(1, 7),
        (4, "won"): Tally(1, 5),
    }


async def test_quarter_buckets_include_lost_deals(dashboard_case: DashboardCase) -> None:
    await dashboard_case.add_deal(forecast="lost", amount=9, day=date(2026, 8, 1))

    assert await _by_quarter(dashboard_case, year=2026) == {(3, "lost"): Tally(1, 9)}


async def test_quarter_buckets_only_cover_the_requested_year(dashboard_case: DashboardCase) -> None:
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await dashboard_case.add_deal(day=day, amount=1)

    found = await _by_quarter(dashboard_case, year=2026)

    assert found == {(1, "pipeline"): Tally(1, 1), (4, "pipeline"): Tally(1, 1)}


async def test_quarter_buckets_follow_owner_and_vendor(dashboard_case: DashboardCase) -> None:
    sap = await dashboard_case.deals.new_vendor("SAP")
    await dashboard_case.add_deal(owner=KIM, amount=1, vendor_id=sap.id)
    await dashboard_case.add_deal(owner=LEE, amount=2, vendor_id=sap.id)
    await dashboard_case.add_deal(owner=KIM, amount=4)

    by_owner = await _by_quarter(dashboard_case, year=2026, owner_user_id=KIM)
    by_vendor = await _by_quarter(dashboard_case, year=2026, vendor_id=sap.id)

    assert by_owner == {(4, "pipeline"): Tally(2, 5)}
    assert by_vendor == {(4, "pipeline"): Tally(2, 3)}


@pytest.mark.parametrize(
    "criteria",
    [
        {},
        {"quarters": frozenset({2})},
        {"year": 2026, "quarters": frozenset({2})},
        {"year": 2026, "quarters": frozenset({1, 3})},
        {"year": 2026, "month": 5},
    ],
    ids=["no-year", "quarter-without-year", "with-quarter", "with-several-quarters", "with-month"],
)
async def test_quarter_tally_rejects_queries_that_are_not_whole_year(
    dashboard_case: DashboardCase, criteria: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match=r"."):
        await dashboard_case.dashboard.tally_by_quarter(DealQuery(**criteria))


async def test_quarter_tally_accepts_all_four_quarters_as_a_whole_year(
    dashboard_case: DashboardCase,
) -> None:
    await dashboard_case.add_deal(day=date(2026, 2, 1), amount=3)

    found = await _by_quarter(dashboard_case, year=2026, quarters=frozenset({1, 2, 3, 4}))

    assert found == {(1, "pipeline"): Tally(1, 3)}


async def test_status_tally_of_separated_quarters_leaves_out_the_gap_quarter(
    dashboard_case: DashboardCase,
) -> None:
    await dashboard_case.add_deal(day=date(2026, 2, 1), amount=1)
    await dashboard_case.add_deal(day=date(2026, 5, 1), amount=10)
    await dashboard_case.add_deal(day=date(2026, 8, 1), amount=100)

    found = await _by_status(dashboard_case, year=2026, quarters=frozenset({1, 3}))

    assert found == {"prospecting": Tally(2, 101)}


# ---- 원장 일치 ----


@pytest.mark.parametrize(
    "query",
    [
        DealQuery(year=2026),
        DealQuery(year=2026, quarters=frozenset({4})),
        DealQuery(year=2026, quarters=frozenset({1, 3})),
        DealQuery(year=2026, owner_user_id=KIM),
        DealQuery(year=2026, forecast_outcome=ForecastOutcomeFilter.NOT_LOST),
        DealQuery(year=2026, quarters=frozenset({4}), forecast_outcome=ForecastOutcomeFilter.OPEN),
        DealQuery(year=2026, month=11, forecast_outcome=ForecastOutcomeFilter.NOT_LOST),
    ],
    ids=[
        "year",
        "quarter",
        "several-quarters",
        "owner",
        "not-lost",
        "quarter-open",
        "month-not-lost",
    ],
)
async def test_status_totals_equal_the_deal_list_ledger_for_the_same_condition(
    dashboard_case: DashboardCase, query: DealQuery
) -> None:
    days = [date(2026, 3, 1), date(2026, 11, 1), date(2026, 11, 30), date(2026, 12, 31)]
    for number, day in enumerate(days * 2):
        await dashboard_case.add_deal(
            owner=KIM if number % 2 == 0 else LEE,
            forecast=("lost", "commit", "won", "pipeline")[number % 4],
            status=("price_negotiation", "poc_completed", None, "introduction")[number % 4],
            amount=10 + number,
            day=day,
        )

    tallies = await dashboard_case.dashboard.tally_by_status(query)
    ledger = await dashboard_case.deals.deals.search(replace(query, limit=200))

    assert sum(t.count for t in tallies.values()) == len(ledger)
    assert sum(t.amount for t in tallies.values()) == sum(
        item.deal.details.revenue_amount.value for item in ledger
    )


async def test_quarter_totals_equal_the_deal_list_ledger_per_quarter(
    dashboard_case: DashboardCase,
) -> None:
    days = [date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1), date(2026, 12, 31)]
    for number, day in enumerate(days * 2):
        await dashboard_case.add_deal(
            forecast=("lost", "commit", "won", "pipeline")[number % 4], amount=10 + number, day=day
        )

    buckets = _quarters(list(await dashboard_case.dashboard.tally_by_quarter(DealQuery(year=2026))))

    for quarter in (1, 2, 3, 4):
        ledger = await dashboard_case.deals.deals.search(
            DealQuery(year=2026, quarters=frozenset({quarter}), limit=200)
        )
        cells = [t for (q, _), t in buckets.items() if q == quarter]
        assert sum(t.count for t in cells) == len(ledger)
        assert sum(t.amount for t in cells) == sum(
            item.deal.details.revenue_amount.value for item in ledger
        )
