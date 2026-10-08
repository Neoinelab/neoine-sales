"""DealRepository.search 동순위 계약: created_at이 같으면 id 오름차순, 경계에 중복·누락이 없다.

Fake와 SQL 구현에 같은 기대값을 적용한다. id를 정렬 기준에서 빼면 SQL은 삽입 순서로 돌아오므로,
삽입을 id 내림차순으로 해서 id 기준이 빠지면 반드시 실패하게 만든다.
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from tests.contracts.conftest import RepositoryCase

SAME_TIME = later(0)
COUNT = 7


async def _add_same_time_deals_in_descending_id_order(case: RepositoryCase) -> list[str]:
    """created_at이 같은 Deal을 id 내림차순으로 저장하고, 기대 순서(id 오름차순)를 돌려준다."""
    deals = [make_deal(SAME_TIME, code=f"T-{n}") for n in range(COUNT)]
    for deal in sorted(deals, key=lambda d: str(d.id), reverse=True):
        await case.add(deal)
    return sorted(str(d.id) for d in deals)


async def _ids(case: RepositoryCase, **criteria: object) -> list[str]:
    found = await case.repository.search(DealQuery(**criteria))  # type: ignore[arg-type]
    return [str(d.id) for d in found]


async def test_search_orders_deals_with_same_created_at_by_id_ascending(
    deal_case: RepositoryCase,
) -> None:
    expected = await _add_same_time_deals_in_descending_id_order(deal_case)

    assert await _ids(deal_case) == expected


async def test_search_pages_over_same_created_at_without_duplicates_or_gaps(
    deal_case: RepositoryCase,
) -> None:
    expected = await _add_same_time_deals_in_descending_id_order(deal_case)

    pages = [await _ids(deal_case, offset=offset, limit=3) for offset in (0, 3, 6)]

    assert [len(page) for page in pages] == [3, 3, 1]
    assert [i for page in pages for i in page] == expected


async def test_search_page_boundary_over_same_created_at_continues_from_previous_page(
    deal_case: RepositoryCase,
) -> None:
    expected = await _add_same_time_deals_in_descending_id_order(deal_case)

    first = await _ids(deal_case, offset=0, limit=4)
    second = await _ids(deal_case, offset=4, limit=4)

    assert first == expected[:4]
    assert second == expected[4:]
