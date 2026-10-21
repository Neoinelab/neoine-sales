"""ListDeals의 확장 필터·정렬(AC-22a~22d, R3): forecast, 연/분기(연도 없는 분기는 올해),
BANT Label, 최종 업데이트 기간, sort/order.

저장소 계약(tests/unit/repositories)이 조건별 세부를 검증하므로 여기서는 유스케이스가 조건을
그대로 전달하고 total·페이지를 함께 돌려주는지를 본다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.domain.bant.values import BantCategory
from tests.support.catalog import label_by_name

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealPage
    from tests.unit.application.deal_env import DealEnv


def _codes(page: DealPage) -> list[str]:
    return [view.item.deal.id.value for view in page.items]


async def test_forecast_matches_the_forecast_key(env: DealEnv) -> None:
    await env.new_deal(forecast_key="pipeline")
    hit = await env.new_deal(forecast_key="commit")

    page = await env.list.execute(DealQuery(forecast_key="commit"))

    assert _codes(page) == [hit.item.deal.id.value]


async def test_an_unknown_forecast_key_is_zero_results_not_an_error(env: DealEnv) -> None:
    await env.new_deal()

    page = await env.list.execute(DealQuery(forecast_key="no_such_forecast"))

    assert (page.items, page.total) == ([], 0)


async def test_year_and_quarter_follow_the_expected_close_with_boundaries(env: DealEnv) -> None:
    days = {
        "q1_end": date(2026, 3, 31),
        "q2_start": date(2026, 4, 1),
        "q2_end": date(2026, 6, 30),
        "q3_start": date(2026, 7, 1),
        "next_year": date(2027, 1, 1),
    }
    views = {name: await env.new_deal(revenue_date=day) for name, day in days.items()}

    page = await env.list.execute(DealQuery(year=2026, quarter=2))

    assert set(_codes(page)) == {views[n].item.deal.id.value for n in ("q2_start", "q2_end")}
    assert page.total == 2


async def _clock_at(env: DealEnv, moment: datetime) -> None:
    env.clock.advance((moment - env.clock.now()).total_seconds())


async def test_quarter_only_filters_this_years_quarter_by_business_date(env: DealEnv) -> None:
    await _clock_at(env, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    this_year = await env.new_deal(revenue_date=date(2026, 5, 20))
    await env.new_deal(revenue_date=date(2025, 5, 20))
    await env.new_deal(revenue_date=date(2027, 5, 20))
    await env.new_deal(revenue_date=date(2026, 8, 20))

    page = await env.list.execute(DealQuery(quarter=2))

    assert _codes(page) == [this_year.item.deal.id.value]
    assert page.total == 1


async def test_quarter_only_follows_the_year_of_the_clock(env: DealEnv) -> None:
    await _clock_at(env, datetime(2027, 7, 15, 12, 0, tzinfo=UTC))
    await env.new_deal(revenue_date=date(2026, 5, 20))
    next_year = await env.new_deal(revenue_date=date(2027, 5, 20))

    page = await env.list.execute(DealQuery(quarter=2))

    assert _codes(page) == [next_year.item.deal.id.value]


async def test_quarter_boundaries_without_a_year_include_both_ends(env: DealEnv) -> None:
    await _clock_at(env, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    q4_start = await env.new_deal(revenue_date=date(2026, 10, 1))
    q4_end = await env.new_deal(revenue_date=date(2026, 12, 31))
    await env.new_deal(revenue_date=date(2026, 9, 30))

    page = await env.list.execute(DealQuery(quarter=4))

    assert set(_codes(page)) == {q4_start.item.deal.id.value, q4_end.item.deal.id.value}


async def test_an_explicit_year_wins_over_the_clock_year(env: DealEnv) -> None:
    await _clock_at(env, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    await env.new_deal(revenue_date=date(2026, 5, 20))
    past = await env.new_deal(revenue_date=date(2025, 5, 20))

    page = await env.list.execute(DealQuery(year=2025, quarter=2))

    assert _codes(page) == [past.item.deal.id.value]


async def test_a_year_alone_includes_the_whole_year(env: DealEnv) -> None:
    inside = await env.new_deal(revenue_date=date(2026, 12, 31))
    await env.new_deal(revenue_date=date(2027, 1, 1))
    await env.new_deal(revenue_date=date(2025, 12, 31))

    page = await env.list.execute(DealQuery(year=2026))

    assert _codes(page) == [inside.item.deal.id.value]


async def test_updated_period_is_combined_with_year_and_quarter(env: DealEnv) -> None:
    env.clock.advance((datetime(2026, 6, 10, 12).astimezone() - env.clock.now()).total_seconds())
    hit = await env.new_deal(revenue_date=date(2026, 5, 20))
    also_hit = await env.new_deal(revenue_date=date(2026, 4, 10))  # 분기 안 + 기간 안
    other_quarter = await env.new_deal(revenue_date=date(2026, 8, 20))
    env.clock.advance(40 * 24 * 3600)
    old_update_excluded = await env.new_deal(revenue_date=date(2026, 5, 21))

    page = await env.list.execute(
        DealQuery(year=2026, quarter=2, updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30))
    )

    codes = set(_codes(page))
    assert {hit.item.deal.id.value, also_hit.item.deal.id.value} <= codes
    assert other_quarter.item.deal.id.value not in codes  # 연/분기는 Expected Close 기준
    assert old_update_excluded.item.deal.id.value not in codes  # 최종 업데이트가 기간 밖
    assert page.total == 2


async def test_bant_labels_of_several_categories_are_combined_with_and(env: DealEnv) -> None:
    full_budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    ceo = await label_by_name(env.uow, BantCategory.AUTHORITY, "CEO 보고 완료")
    both = await env.new_deal(
        bant={BantCategory.BUDGET: full_budget.id, BantCategory.AUTHORITY: ceo.id}
    )
    await env.new_deal(bant={BantCategory.BUDGET: full_budget.id})
    await env.new_deal(bant={BantCategory.AUTHORITY: ceo.id})

    only_budget = await env.list.execute(
        DealQuery(bant_label_ids={BantCategory.BUDGET: full_budget.id})
    )
    page = await env.list.execute(
        DealQuery(
            bant_label_ids={BantCategory.BUDGET: full_budget.id, BantCategory.AUTHORITY: ceo.id}
        )
    )

    assert only_budget.total == 2
    assert _codes(page) == [both.item.deal.id.value]


async def test_sorting_and_ordering_reach_the_repository_and_total_ignores_the_page(
    env: DealEnv,
) -> None:
    cheap = await env.new_deal(revenue_amount=100)
    middle = await env.new_deal(revenue_amount=200)
    rich = await env.new_deal(revenue_amount=300)

    ascending = await env.list.execute(DealQuery(sort=DealSort.REVENUE_AMOUNT, order=SortOrder.ASC))
    descending_page = await env.list.execute(
        DealQuery(sort=DealSort.REVENUE_AMOUNT, order=SortOrder.DESC, offset=1, limit=1)
    )

    assert _codes(ascending) == [v.item.deal.id.value for v in (cheap, middle, rich)]
    assert _codes(descending_page) == [middle.item.deal.id.value]
    assert descending_page.total == 3


async def test_sorting_by_status_follows_the_current_status_order(env: DealEnv) -> None:
    late = await env.new_deal(status_key="price_negotiation")
    early = await env.new_deal(status_key="prospecting")

    page = await env.list.execute(DealQuery(sort=DealSort.STATUS, order=SortOrder.ASC))

    assert _codes(page) == [early.item.deal.id.value, late.item.deal.id.value]


@pytest.mark.parametrize(
    ("tz", "moment", "expected_year"),
    [
        # UTC로는 2026-12-31이지만 서울(UTC+9)의 업무 날짜는 2027-01-01
        ("Asia/Seoul", datetime(2026, 12, 31, 16, 0, tzinfo=UTC), 2027),
        # UTC로는 2027-01-01이지만 로스앤젤레스(UTC-8)의 업무 날짜는 2026-12-31
        ("America/Los_Angeles", datetime(2027, 1, 1, 3, 0, tzinfo=UTC), 2026),
    ],
)
async def test_quarter_only_uses_the_business_date_year_across_new_year(
    env: DealEnv,
    local_tz: Callable[[str], None],
    tz: str,
    moment: datetime,
    expected_year: int,
) -> None:
    local_tz(tz)
    await _clock_at(env, moment)
    in_business_year = await env.new_deal(revenue_date=date(expected_year, 2, 10))
    await env.new_deal(revenue_date=date(2026 if expected_year == 2027 else 2027, 2, 10))

    page = await env.list.execute(DealQuery(quarter=1))

    assert _codes(page) == [in_business_year.item.deal.id.value]
