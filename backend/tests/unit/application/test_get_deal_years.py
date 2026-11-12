"""GetDealYears(R2 AC2-1): Expected Close가 가장 이른 Deal의 연도만 사실로 돌려준다."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal.deal_years import DealYearsView, GetDealYears
from tests.factories_deal import SALES, make_patch

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_deal_years_returns_earliest_revenue_year(env: DealEnv) -> None:
    """Expected Close가 가장 이른 Deal의 연도를 돌려준다."""
    # given: Expected Close 연도가 2024·2019·2027인 Deal 세 개
    for revenue_date in (date(2024, 5, 1), date(2019, 12, 31), date(2027, 1, 1)):
        await env.new_deal(revenue_date=revenue_date)

    # when: 연도 정보를 조회한다
    view = await GetDealYears(env.uow_factory).execute()

    # then: 가장 이른 연도 2019다
    assert view == DealYearsView(earliest_year=2019)


async def test_deal_years_is_none_without_deals(env: DealEnv) -> None:
    """Deal이 없으면 가장 이른 연도는 없다."""
    # when: Deal 없이 연도 정보를 조회한다
    view = await GetDealYears(env.uow_factory).execute()

    # then: earliest_year는 None이다
    assert view == DealYearsView(earliest_year=None)


async def test_deal_years_with_one_deal_is_that_deals_year(env: DealEnv) -> None:
    """Deal이 하나면 그 Deal의 연도다."""
    # given: 2031년 Expected Close인 Deal 하나
    await env.new_deal(revenue_date=date(2031, 3, 4))

    # when: 연도 정보를 조회한다
    view = await GetDealYears(env.uow_factory).execute()

    # then: 2031이다
    assert view.earliest_year == 2031


async def test_deal_years_follows_a_revenue_date_update(env: DealEnv) -> None:
    """Expected Close를 수정하면 조회 결과가 바로 따라간다."""
    # given: 2026년 Expected Close인 Deal
    deal = await env.new_deal(revenue_date=date(2026, 6, 30))
    before = await GetDealYears(env.uow_factory).execute()

    # when: Expected Close를 2022년으로 수정하고 다시 조회한다
    await env.update.execute(
        deal.item.deal.id.value, make_patch(revenue_date=date(2022, 1, 2)), SALES
    )
    after = await GetDealYears(env.uow_factory).execute()

    # then: 수정 전 2026, 수정 후 2022다
    assert before.earliest_year == 2026
    assert after.earliest_year == 2022


async def test_deal_years_does_not_write(env: DealEnv) -> None:
    """연도 조회는 아무것도 저장하지 않는다."""
    # given: Deal 하나와 지금까지의 커밋 수
    await env.new_deal(revenue_date=date(2024, 5, 1))
    commits = env.uow.commits

    # when: 연도 정보를 조회한다
    await GetDealYears(env.uow_factory).execute()

    # then: 커밋 수가 그대로다
    assert env.uow.commits == commits
