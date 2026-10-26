"""GetDealYears(R2 AC2-1): Expected Close가 가장 이른 Deal의 연도만 사실로 돌려준다."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal.deal_years import DealYearsView, GetDealYears

from tests.factories_deal import SALES, make_patch

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_deal_years_returns_earliest_revenue_year(env: DealEnv) -> None:
    for revenue_date in (date(2024, 5, 1), date(2019, 12, 31), date(2027, 1, 1)):
        await env.new_deal(revenue_date=revenue_date)

    view = await GetDealYears(env.uow_factory).execute()

    assert view == DealYearsView(earliest_year=2019)


async def test_deal_years_is_none_without_deals(env: DealEnv) -> None:
    view = await GetDealYears(env.uow_factory).execute()

    assert view == DealYearsView(earliest_year=None)


async def test_deal_years_with_one_deal_is_that_deals_year(env: DealEnv) -> None:
    await env.new_deal(revenue_date=date(2031, 3, 4))

    view = await GetDealYears(env.uow_factory).execute()

    assert view.earliest_year == 2031


async def test_deal_years_follows_a_revenue_date_update(env: DealEnv) -> None:
    deal = await env.new_deal(revenue_date=date(2026, 6, 30))
    assert (await GetDealYears(env.uow_factory).execute()).earliest_year == 2026

    await env.update.execute(
        deal.item.deal.id.value, make_patch(revenue_date=date(2022, 1, 2)), SALES
    )

    assert (await GetDealYears(env.uow_factory).execute()).earliest_year == 2022


async def test_deal_years_does_not_write(env: DealEnv) -> None:
    await env.new_deal(revenue_date=date(2024, 5, 1))
    commits = env.uow.commits

    await GetDealYears(env.uow_factory).execute()

    assert env.uow.commits == commits
