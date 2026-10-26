"""DealRepository.earliest_revenue_year 계약(R2 AC2-1·2-6): Fake와 SQL에 같은 기대값.

Expected Close(revenue_date)가 가장 이른 Deal의 연도만 돌려준다. Deal이 없으면 None이고, 삭제·수정을
바로 반영한다(저장된 값에서 매번 센다).
"""

from datetime import date
from typing import TYPE_CHECKING

from tests.factories import make_deal, make_deal_details

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


async def test_earliest_revenue_year_is_none_without_deals(deal_case: DealCase) -> None:
    assert await deal_case.deals.earliest_revenue_year() is None


async def test_earliest_revenue_year_is_the_minimum_year(deal_case: DealCase) -> None:
    for code, day in (
        ("20261016-A001", date(2026, 1, 1)),
        ("20261016-A002", date(2023, 12, 31)),
        ("20261016-A003", date(2023, 1, 1)),
    ):
        await deal_case.add(make_deal(code=code, revenue_date=day))

    assert await deal_case.deals.earliest_revenue_year() == 2023


async def test_earliest_revenue_year_follows_deletion(deal_case: DealCase) -> None:
    oldest = make_deal(code="20261016-A001", revenue_date=date(2019, 5, 1))
    await deal_case.add(oldest)
    await deal_case.add(make_deal(code="20261016-A002", revenue_date=date(2024, 5, 1)))
    assert await deal_case.deals.earliest_revenue_year() == 2019

    await deal_case.deals.delete(oldest.id)

    assert await deal_case.deals.earliest_revenue_year() == 2024


async def test_earliest_revenue_year_follows_update(deal_case: DealCase) -> None:
    deal = make_deal(code="20261016-A001", revenue_date=date(2026, 6, 30))
    await deal_case.add(deal)
    await deal_case.add(make_deal(code="20261016-A002", revenue_date=date(2025, 6, 30)))
    assert await deal_case.deals.earliest_revenue_year() == 2025

    await deal_case.revise(deal.id, details=make_deal_details(revenue_date=date(2021, 2, 3)))

    assert await deal_case.deals.earliest_revenue_year() == 2021


async def test_earliest_revenue_year_is_none_after_the_last_deal_is_deleted(
    deal_case: DealCase,
) -> None:
    deal = make_deal(code="20261016-A001", revenue_date=date(2026, 6, 30))
    await deal_case.add(deal)

    await deal_case.deals.delete(deal.id)

    assert await deal_case.deals.earliest_revenue_year() is None
