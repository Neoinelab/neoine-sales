"""ListDeals 확장 필터·정렬 중 BDD 케이스(DL)가 덮지 않는 세부 동작.

Forecast·연/분기·정렬 케이스는 `test_deal_list_search_cases.py`·
`test_deal_list_period_sort_cases.py`가 정본이다. 여기에는 그 케이스에 없는 단언
(연도 없는 분기의 양끝, 명시 연도 우선, 기간+연/분기 조합,
정렬+페이지 total, 시간대별 새해 경계)만 남겼다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealPage
    from tests.unit.application.deal_env import DealEnv


def _codes(page: DealPage) -> list[str]:
    return [view.item.deal.id.value for view in page.items]


async def _clock_at(env: DealEnv, moment: datetime) -> None:
    env.clock.advance((moment - env.clock.now()).total_seconds())


async def test_quarter_boundaries_without_a_year_include_both_ends(env: DealEnv) -> None:
    """연도 없이 분기만 주면 올해 그 분기의 첫날과 마지막 날을 포함한다."""
    # given: 올해 Q4 첫날·마지막 날 Deal과 Q3 마지막 날 Deal
    await _clock_at(env, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    q4_start = await env.new_deal(revenue_date=date(2026, 10, 1))
    q4_end = await env.new_deal(revenue_date=date(2026, 12, 31))
    await env.new_deal(revenue_date=date(2026, 9, 30))

    # when: 연도 없이 Q4만 조회한다
    page = await env.list.execute(DealQuery(quarters=frozenset({4})))

    # then: Q4 경계 두 날의 Deal만 나온다
    assert set(_codes(page)) == {q4_start.item.deal.id.value, q4_end.item.deal.id.value}


async def test_an_explicit_year_wins_over_the_clock_year(env: DealEnv) -> None:
    """연도를 명시하면 시계의 올해보다 그 연도가 우선한다."""
    # given: 시계는 2026년이고 2026·2025년 Q2 Deal이 있다
    await _clock_at(env, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    await env.new_deal(revenue_date=date(2026, 5, 20))
    past = await env.new_deal(revenue_date=date(2025, 5, 20))

    # when: 2025년 Q2로 조회한다
    page = await env.list.execute(DealQuery(year=2025, quarters=frozenset({2})))

    # then: 2025년 Deal만 나온다
    assert _codes(page) == [past.item.deal.id.value]


async def test_updated_period_is_combined_with_year_and_quarter(env: DealEnv) -> None:
    """최종 업데이트 기간은 연/분기(Expected Close 기준)와 AND로 결합한다."""
    # given: 6월 초에 갱신된 Q2 Deal 둘, 다른 분기 Deal, 40일 뒤 갱신된 Q2 Deal
    env.clock.advance((datetime(2026, 6, 10, 12).astimezone() - env.clock.now()).total_seconds())
    hit = await env.new_deal(revenue_date=date(2026, 5, 20))
    also_hit = await env.new_deal(revenue_date=date(2026, 4, 10))
    other_quarter = await env.new_deal(revenue_date=date(2026, 8, 20))
    env.clock.advance(40 * 24 * 3600)
    old_update_excluded = await env.new_deal(revenue_date=date(2026, 5, 21))

    # when: 2026 Q2와 6월 갱신 기간으로 조회한다
    page = await env.list.execute(
        DealQuery(
            year=2026,
            quarters=frozenset({2}),
            updated_from=date(2026, 6, 1),
            updated_to=date(2026, 6, 30),
        )
    )

    # then: 분기와 기간을 모두 만족하는 두 Deal만 나온다
    codes = set(_codes(page))
    assert {hit.item.deal.id.value, also_hit.item.deal.id.value} <= codes
    assert other_quarter.item.deal.id.value not in codes
    assert old_update_excluded.item.deal.id.value not in codes
    assert page.total == 2


async def test_sorting_and_ordering_reach_the_repository_and_total_ignores_the_page(
    env: DealEnv,
) -> None:
    """정렬 기준·방향이 저장소에 전달되고 total은 페이지와 무관하다."""
    # given: 금액이 다른 Deal 셋
    cheap = await env.new_deal(revenue_amount=100)
    middle = await env.new_deal(revenue_amount=200)
    rich = await env.new_deal(revenue_amount=300)

    # when: 금액 오름차순 전체와, 내림차순 둘째 한 건을 조회한다
    ascending = await env.list.execute(DealQuery(sort=DealSort.REVENUE_AMOUNT, order=SortOrder.ASC))
    descending_page = await env.list.execute(
        DealQuery(sort=DealSort.REVENUE_AMOUNT, order=SortOrder.DESC, offset=1, limit=1)
    )

    # then: 오름차순 순서이고 내림차순 둘째는 middle이며 total은 3이다
    assert _codes(ascending) == [v.item.deal.id.value for v in (cheap, middle, rich)]
    assert _codes(descending_page) == [middle.item.deal.id.value]
    assert descending_page.total == 3


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
    """연도 없는 분기는 서버 시간대의 업무 날짜 연도를 쓴다(UTC와 해가 다른 새해 경계)."""
    # given: 서버 시간대와 새해 경계 시각, 두 해의 Q1 Deal
    local_tz(tz)
    await _clock_at(env, moment)
    in_business_year = await env.new_deal(revenue_date=date(expected_year, 2, 10))
    await env.new_deal(revenue_date=date(2026 if expected_year == 2027 else 2027, 2, 10))

    # when: 연도 없이 Q1만 조회한다
    page = await env.list.execute(DealQuery(quarters=frozenset({1})))

    # then: 업무 날짜 연도의 Q1 Deal만 나온다
    assert _codes(page) == [in_business_year.item.deal.id.value]
