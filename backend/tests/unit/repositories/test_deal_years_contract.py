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
    """Deal이 없으면 가장 이른 연도는 None이다."""
    # when: Deal 없이 가장 이른 연도를 조회한다
    year = await deal_case.deals.earliest_revenue_year()

    # then: None이다
    assert year is None


async def test_earliest_revenue_year_is_the_minimum_year(deal_case: DealCase) -> None:
    """가장 이른 Expected Close의 연도를 돌려준다."""
    # given: 2026·2023·2023년 Expected Close인 Deal 세 개
    for code, day in (
        ("20261016-A001", date(2026, 1, 1)),
        ("20261016-A002", date(2023, 12, 31)),
        ("20261016-A003", date(2023, 1, 1)),
    ):
        await deal_case.add(make_deal(code=code, revenue_date=day))

    # when: 가장 이른 연도를 조회한다
    year = await deal_case.deals.earliest_revenue_year()

    # then: 2023이다
    assert year == 2023


async def test_earliest_revenue_year_follows_deletion(deal_case: DealCase) -> None:
    """가장 이른 Deal을 삭제하면 다음으로 이른 연도가 된다."""
    # given: 2019년 Deal과 2024년 Deal
    oldest = make_deal(code="20261016-A001", revenue_date=date(2019, 5, 1))
    await deal_case.add(oldest)
    await deal_case.add(make_deal(code="20261016-A002", revenue_date=date(2024, 5, 1)))
    before = await deal_case.deals.earliest_revenue_year()

    # when: 2019년 Deal을 삭제하고 다시 조회한다
    await deal_case.deals.delete(oldest.id)
    after = await deal_case.deals.earliest_revenue_year()

    # then: 삭제 전 2019, 삭제 후 2024다
    assert before == 2019
    assert after == 2024


async def test_earliest_revenue_year_follows_update(deal_case: DealCase) -> None:
    """Expected Close를 수정하면 가장 이른 연도가 바로 바뀐다."""
    # given: 2026년 Deal과 2025년 Deal
    deal = make_deal(code="20261016-A001", revenue_date=date(2026, 6, 30))
    await deal_case.add(deal)
    await deal_case.add(make_deal(code="20261016-A002", revenue_date=date(2025, 6, 30)))
    before = await deal_case.deals.earliest_revenue_year()

    # when: 2026년 Deal의 Expected Close를 2021년으로 수정하고 다시 조회한다
    await deal_case.revise(deal.id, details=make_deal_details(revenue_date=date(2021, 2, 3)))
    after = await deal_case.deals.earliest_revenue_year()

    # then: 수정 전 2025, 수정 후 2021이다
    assert before == 2025
    assert after == 2021


async def test_earliest_revenue_year_is_none_after_the_last_deal_is_deleted(
    deal_case: DealCase,
) -> None:
    """마지막 Deal을 삭제하면 가장 이른 연도는 None이다."""
    # given: Deal 하나
    deal = make_deal(code="20261016-A001", revenue_date=date(2026, 6, 30))
    await deal_case.add(deal)

    # when: 그 Deal을 삭제하고 조회한다
    await deal_case.deals.delete(deal.id)
    year = await deal_case.deals.earliest_revenue_year()

    # then: None이다
    assert year is None
