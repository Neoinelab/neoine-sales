"""DashboardTallyRepository 계약: Fake와 SQL에 같은 기대값.

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
    """Deal이 없으면 Status 집계가 비어 있다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 0 채우기는 도메인이 한다.
    """
    # when: Deal 없이 2026년을 집계한다
    found = await _by_status(dashboard_case, year=2026)

    # then: 비어 있다
    assert found == {}


async def test_deals_are_grouped_by_status_key_with_count_and_amount(
    dashboard_case: DashboardCase,
) -> None:
    """Deal은 Status key별 건수와 revenue_amount 합으로 묶인다.

    BDD 밖: 저장소 계약(Fake·SQL 공통).
    """
    # given: 기회발굴 Deal 둘(100·40)과 POC완료 Deal 하나(7)
    await dashboard_case.add_deal(status="prospecting", amount=100)
    await dashboard_case.add_deal(status="prospecting", amount=40)
    await dashboard_case.add_deal(status="poc_completed", amount=7)

    # when: 2026년을 집계한다
    found = await _by_status(dashboard_case, year=2026)

    # then: Status별 건수·금액 합이다
    assert found == {"prospecting": Tally(2, 140), "poc_completed": Tally(1, 7)}


async def test_status_keys_without_deals_are_absent(dashboard_case: DashboardCase) -> None:
    """Deal이 없는 Status key는 집계에 없다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 0 채우기는 도메인이 한다.
    """
    # given: 소개 Status Deal 하나
    await dashboard_case.add_deal(status="introduction", amount=1)

    # when: 2026년을 집계한다
    found = await _by_status(dashboard_case, year=2026)

    # then: 소개만 있다
    assert set(found) == {"introduction"}


async def test_amounts_beyond_32_bits_are_summed_exactly_by_status(
    dashboard_case: DashboardCase,
) -> None:
    """32비트를 넘는 금액도 Status별 합이 정확하다.

    테스트 코드: DSH-024
    """
    # given: 같은 Status의 Deal 둘, 2^40원과 2^40+1원
    big = 2**40
    await dashboard_case.add_deal(amount=big)
    await dashboard_case.add_deal(amount=big + 1)

    # when: 2026년을 집계한다
    found = await _by_status(dashboard_case, year=2026)

    # then: 합이 정확하다
    assert found == {"prospecting": Tally(2, 2 * big + 1)}


async def test_status_tally_with_not_lost_filter_drops_only_lost_deals(
    dashboard_case: DashboardCase,
) -> None:
    """Lost 제외 조건은 Lost Deal만 뺀다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R7(DSH-011)의 SQL 쪽 확인이다.
    """
    # given: Pipeline·Commit·Won·Lost Deal
    await dashboard_case.add_deal(forecast="pipeline", amount=1)
    await dashboard_case.add_deal(forecast="commit", amount=2, status="price_negotiation")
    await dashboard_case.add_deal(forecast="won", amount=4)
    await dashboard_case.add_deal(forecast="lost", amount=8, status="price_negotiation")

    # when: Lost 제외 조건으로 집계한다
    found = await _by_status(
        dashboard_case, year=2026, forecast_outcome=ForecastOutcomeFilter.NOT_LOST
    )

    # then: Lost인 8원은 빠진다
    assert found == {
        "prospecting": Tally(1, 1),
        "price_negotiation": Tally(1, 2),
        "contract_completed": Tally(1, 4),
    }


async def test_status_tally_period_bounds_are_inclusive(dashboard_case: DashboardCase) -> None:
    """기간 양끝(12-31·01-01)은 포함이고 연·분기·월 조건이 그에 맞다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R5(DSH-013)의 SQL 쪽 확인이다.
    """
    # given: Expected Close가 2025-12-31, 2026-01-01, 2026-12-31, 2027-01-01인 Deal
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await dashboard_case.add_deal(day=day, amount=1)

    # when: 2026년, 2026 Q4, 2027년 1월로 집계한다
    year = await _by_status(dashboard_case, year=2026)
    q4 = await _by_status(dashboard_case, year=2026, quarters=frozenset({4}))
    jan = await _by_status(dashboard_case, year=2027, month=1)

    # then: 2026년은 01-01·12-31 둘, Q4는 12-31, 2027-01은 01-01 하나다
    assert year == {"prospecting": Tally(2, 2)}
    assert q4 == {"prospecting": Tally(1, 1)}
    assert jan == {"prospecting": Tally(1, 1)}


async def test_status_tally_owner_and_vendor_conditions_are_anded(
    dashboard_case: DashboardCase,
) -> None:
    """담당자와 Vendor 조건은 함께 주면 AND다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R5(DSH-012)의 SQL 쪽 확인이다.
    """
    # given: KIM·SAP, KIM, LEE·SAP Deal
    sap = await dashboard_case.deals.new_vendor("SAP")
    await dashboard_case.add_deal(owner=KIM, vendor_id=sap.id, amount=1)
    await dashboard_case.add_deal(owner=KIM, amount=2)
    await dashboard_case.add_deal(owner=LEE, vendor_id=sap.id, amount=4)

    # when: KIM + SAP, KIM만으로 집계한다
    both = await _by_status(dashboard_case, year=2026, owner_user_id=KIM, vendor_id=sap.id)
    owner = await _by_status(dashboard_case, year=2026, owner_user_id=KIM)

    # then: 둘 다 맞는 Deal 하나, KIM의 Deal 둘이다
    assert both == {"prospecting": Tally(1, 1)}
    assert owner == {"prospecting": Tally(2, 3)}


async def test_status_tally_ignores_page_and_sort(dashboard_case: DashboardCase) -> None:
    """집계는 목록의 페이지·정렬 조건을 무시한다.

    BDD 밖: 저장소 계약(Fake·SQL 공통).
    """
    # given: 같은 Status의 Deal 5건
    for number in range(5):
        await dashboard_case.add_deal(amount=10 + number)

    # when: 세 번째부터 한 건만 보는 페이지 조건으로 집계한다
    found = await dashboard_case.dashboard.tally_by_status(DealQuery(year=2026, offset=3, limit=1))

    # then: 5건 전부 센다
    assert dict(found) == {"prospecting": Tally(5, 60)}


async def test_status_tally_with_a_risk_filter_needs_a_risk_basis(
    dashboard_case: DashboardCase,
) -> None:
    """기한초과·미업데이트 조건에 판정 기준이 없으면 오류다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 판정 기준 누락을 조용히 넘기지 않는다.
    """
    # given: Deal 하나
    await dashboard_case.add_deal()

    # when·then: 판정 기준 없이 기한초과 조건으로 집계하면 ValueError다
    with pytest.raises(ValueError, match=r"."):
        await dashboard_case.dashboard.tally_by_status(DealQuery(overdue=True))


async def test_status_tally_with_a_risk_filter_and_basis_counts_matching_deals(
    dashboard_case: DashboardCase,
) -> None:
    """판정 기준이 있으면 미업데이트 Deal만 집계한다.

    BDD 밖: 저장소 계약(Fake·SQL 공통).
    """
    # given: 등록 시각이 오래 지난 Deal 하나와 판정 기준(오늘 2026-11-30, 14일)
    from app.domain.deal.risk import RiskBasis  # noqa: PLC0415

    await dashboard_case.add_deal(amount=3)
    basis = RiskBasis(today=date(2026, 11, 30), stale_days=14)

    # when: 미업데이트 조건으로 집계한다
    found = await dashboard_case.dashboard.tally_by_status(DealQuery(stale=True, risk_basis=basis))

    # then: 그 Deal이 집계된다
    assert dict(found) == {"prospecting": Tally(1, 3)}


# ---- tally_by_quarter ----


async def test_no_deals_gives_no_quarter_buckets(dashboard_case: DashboardCase) -> None:
    """Deal이 없으면 분기 집계가 비어 있다.

    BDD 밖: 저장소 계약(Fake·SQL 공통).
    """
    # when: Deal 없이 2026년을 분기별로 집계한다
    found = await _by_quarter(dashboard_case, year=2026)

    # then: 비어 있다
    assert found == {}


async def test_deals_are_grouped_by_quarter_and_forecast_key(
    dashboard_case: DashboardCase,
) -> None:
    """Deal은 Expected Close 분기와 Forecast key별로 묶인다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R8(DSH-014)의 SQL 쪽 확인이다.
    """
    # given: Q1 Pipeline 둘, Q2 Commit, Q4 Won
    await dashboard_case.add_deal(forecast="pipeline", amount=100, day=date(2026, 2, 1))
    await dashboard_case.add_deal(forecast="pipeline", amount=40, day=date(2026, 3, 31))
    await dashboard_case.add_deal(forecast="commit", amount=7, day=date(2026, 4, 1))
    await dashboard_case.add_deal(forecast="won", amount=5, day=date(2026, 12, 31))

    # when: 2026년을 분기별로 집계한다
    found = await _by_quarter(dashboard_case, year=2026)

    # then: (분기, key)별 건수·금액이다
    assert found == {
        (1, "pipeline"): Tally(2, 140),
        (2, "commit"): Tally(1, 7),
        (4, "won"): Tally(1, 5),
    }


async def test_quarter_buckets_include_lost_deals(dashboard_case: DashboardCase) -> None:
    """분기 집계는 Lost Deal도 포함한다(도메인이 열에서 뺀다).

    BDD 밖: 저장소 계약(Fake·SQL 공통).
    """
    # given: Q3 Lost Deal 하나
    await dashboard_case.add_deal(forecast="lost", amount=9, day=date(2026, 8, 1))

    # when: 2026년을 분기별로 집계한다
    found = await _by_quarter(dashboard_case, year=2026)

    # then: Lost가 집계에 있다
    assert found == {(3, "lost"): Tally(1, 9)}


async def test_quarter_buckets_only_cover_the_requested_year(dashboard_case: DashboardCase) -> None:
    """분기 집계는 요청한 연도의 Deal만 센다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R5(DSH-013)의 SQL 쪽 확인이다.
    """
    # given: Expected Close가 2025-12-31, 2026-01-01, 2026-12-31, 2027-01-01인 Deal
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await dashboard_case.add_deal(day=day, amount=1)

    # when: 2026년을 분기별로 집계한다
    found = await _by_quarter(dashboard_case, year=2026)

    # then: 2026-01-01(Q1)과 2026-12-31(Q4)만 있다
    assert found == {(1, "pipeline"): Tally(1, 1), (4, "pipeline"): Tally(1, 1)}


async def test_quarter_buckets_follow_owner_and_vendor(dashboard_case: DashboardCase) -> None:
    """분기 집계는 담당자·Vendor 조건을 따른다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R8(DSH-015)의 SQL 쪽 확인이다.
    """
    # given: KIM·SAP, LEE·SAP, KIM Deal
    sap = await dashboard_case.deals.new_vendor("SAP")
    await dashboard_case.add_deal(owner=KIM, amount=1, vendor_id=sap.id)
    await dashboard_case.add_deal(owner=LEE, amount=2, vendor_id=sap.id)
    await dashboard_case.add_deal(owner=KIM, amount=4)

    # when: KIM으로, SAP로 각각 분기별 집계한다
    by_owner = await _by_quarter(dashboard_case, year=2026, owner_user_id=KIM)
    by_vendor = await _by_quarter(dashboard_case, year=2026, vendor_id=sap.id)

    # then: KIM은 5원, SAP는 3원이다
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
    """분기 집계는 연 단위 질의가 아니면 오류다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 고른 분기가 분기 행에 새는 실수를 막는다.
    """
    # when·then: 연 단위가 아닌 조건으로 분기 집계하면 ValueError다
    with pytest.raises(ValueError, match=r"."):
        await dashboard_case.dashboard.tally_by_quarter(DealQuery(**criteria))


async def test_quarter_tally_accepts_all_four_quarters_as_a_whole_year(
    dashboard_case: DashboardCase,
) -> None:
    """네 분기를 모두 준 조건은 연 전체로 받아들인다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 넷 다 = 분기 조건 없음(DSH-R2).
    """
    # given: Q1 Deal 하나
    await dashboard_case.add_deal(day=date(2026, 2, 1), amount=3)

    # when: 분기 1~4를 준 조건으로 분기별 집계한다
    found = await _by_quarter(dashboard_case, year=2026, quarters=frozenset({1, 2, 3, 4}))

    # then: 집계된다
    assert found == {(1, "pipeline"): Tally(1, 3)}


async def test_status_tally_of_separated_quarters_leaves_out_the_gap_quarter(
    dashboard_case: DashboardCase,
) -> None:
    """떨어진 분기(Q1·Q3)를 고르면 사이의 Q2는 집계에서 빠진다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R4·R5(DSH-006, DSH-009)의 SQL 쪽 확인이다.
    """
    # given: Q1·Q2·Q3에 Deal이 하나씩 있다
    await dashboard_case.add_deal(day=date(2026, 2, 1), amount=1)
    await dashboard_case.add_deal(day=date(2026, 5, 1), amount=10)
    await dashboard_case.add_deal(day=date(2026, 8, 1), amount=100)

    # when: Q1·Q3로 Status를 집계한다
    found = await _by_status(dashboard_case, year=2026, quarters=frozenset({1, 3}))

    # then: Q2의 10원은 빠진다
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
    """Status 집계의 합은 같은 조건 Deal 목록 원장의 건수·금액과 같다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R11(DSH-022)의 SQL 쪽 확인이다.
    """
    # given: 담당자·Forecast·Status·날짜가 섞인 Deal 8건
    days = [date(2026, 3, 1), date(2026, 11, 1), date(2026, 11, 30), date(2026, 12, 31)]
    for number, day in enumerate(days * 2):
        await dashboard_case.add_deal(
            owner=KIM if number % 2 == 0 else LEE,
            forecast=("lost", "commit", "won", "pipeline")[number % 4],
            status=("price_negotiation", "poc_completed", None, "introduction")[number % 4],
            amount=10 + number,
            day=day,
        )

    # when: 조건으로 Status 집계하고 같은 조건으로 Deal 목록을 조회한다
    tallies = await dashboard_case.dashboard.tally_by_status(query)
    ledger = await dashboard_case.deals.deals.search(replace(query, limit=200))

    # then: 집계 합이 목록의 건수·금액 합과 같다
    assert sum(t.count for t in tallies.values()) == len(ledger)
    assert sum(t.amount for t in tallies.values()) == sum(
        item.deal.details.revenue_amount.value for item in ledger
    )


async def test_quarter_totals_equal_the_deal_list_ledger_per_quarter(
    dashboard_case: DashboardCase,
) -> None:
    """분기 집계의 분기별 합은 그 분기 Deal 목록 원장과 같다.

    BDD 밖: 저장소 계약(Fake·SQL 공통). 규칙 DSH-R11(DSH-022)의 SQL 쪽 확인이다.
    """
    # given: 분기 경계일에 걸친 Forecast가 섞인 Deal 8건
    days = [date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1), date(2026, 12, 31)]
    for number, day in enumerate(days * 2):
        await dashboard_case.add_deal(
            forecast=("lost", "commit", "won", "pipeline")[number % 4], amount=10 + number, day=day
        )

    # when: 2026년을 분기별로 집계한다
    buckets = _quarters(list(await dashboard_case.dashboard.tally_by_quarter(DealQuery(year=2026))))

    # then: 분기마다 집계 합이 그 분기 Deal 목록의 건수·금액 합과 같다
    for quarter in (1, 2, 3, 4):
        ledger = await dashboard_case.deals.deals.search(
            DealQuery(year=2026, quarters=frozenset({quarter}), limit=200)
        )
        cells = [t for (q, _), t in buckets.items() if q == quarter]
        assert sum(t.count for t in cells) == len(ledger)
        assert sum(t.amount for t in cells) == sum(
            item.deal.details.revenue_amount.value for item in ledger
        )
