"""DealRepository.facets 계약(R3, AC-24, R2 리뷰 이월 1): Fake와 SQL(PostgreSQL)에 같은 기대값.

(Vendor 목록, Solution 목록)은 빈 문자열을 뺀 중복 없는 값이고 대소문자 무시(lower) 순이다. SQL은
`SELECT DISTINCT`와 lower 정렬을 함께 쓸 때 PostgreSQL이 거절하는 형태(42P10)를 쓰면 안 된다.
계약은 대소문자만 다른 값이 서로 다른 항목인지 같은 항목인지에 기대지 않는다(DB 정렬 규칙 차이).
"""

from typing import TYPE_CHECKING

from tests.factories import later, make_deal

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


async def _add(case: DealCase, number: int, vendor: str, solution: str) -> None:
    await case.add(
        make_deal(later(number), code=f"20261016-A{number:03d}", vendor=vendor, solution=solution)
    )


async def test_an_empty_repository_has_no_facets(deal_case: DealCase) -> None:
    vendors, solutions = await deal_case.deals.facets()

    assert (list(vendors), list(solutions)) == ([], [])


async def test_the_values_are_distinct_and_sorted_ignoring_case(deal_case: DealCase) -> None:
    await _add(deal_case, 1, "sap", "Zeta")
    await _add(deal_case, 2, "Oracle", "alpha")
    await _add(deal_case, 3, "sap", "Beta")
    await _add(deal_case, 4, "Microsoft", "alpha")

    vendors, solutions = await deal_case.deals.facets()

    assert list(vendors) == ["Microsoft", "Oracle", "sap"]
    assert list(solutions) == ["alpha", "Beta", "Zeta"]


async def test_blank_values_are_left_out(deal_case: DealCase) -> None:
    await _add(deal_case, 1, "", "")
    await _add(deal_case, 2, "SAP", "")
    await _add(deal_case, 3, "", "S/4HANA")

    vendors, solutions = await deal_case.deals.facets()

    assert (list(vendors), list(solutions)) == (["SAP"], ["S/4HANA"])


async def test_vendors_and_solutions_are_independent_lists(deal_case: DealCase) -> None:
    await _add(deal_case, 1, "SAP", "Cloud")
    await _add(deal_case, 2, "Cloud", "SAP")

    vendors, solutions = await deal_case.deals.facets()

    assert list(vendors) == ["Cloud", "SAP"]
    assert list(solutions) == ["Cloud", "SAP"]


async def test_the_values_follow_edits_and_deletions(deal_case: DealCase) -> None:
    await _add(deal_case, 1, "SAP", "ERP")
    await _add(deal_case, 2, "Oracle", "DB")
    deal = await deal_case.deals.get(make_deal(code="20261016-A001").id)
    details = deal.details
    await deal_case.revise(
        deal.id,
        details=make_deal(vendor="Microsoft", solution=details.solution).details,
    )
    await deal_case.deals.delete(make_deal(code="20261016-A002").id)

    vendors, solutions = await deal_case.deals.facets()

    assert (list(vendors), list(solutions)) == (["Microsoft"], ["ERP"])


async def test_hangul_values_are_listed(deal_case: DealCase) -> None:
    await _add(deal_case, 1, "나무", "다래")
    await _add(deal_case, 2, "가람", "다래")

    vendors, solutions = await deal_case.deals.facets()

    assert list(vendors) == ["가람", "나무"]
    assert list(solutions) == ["다래"]
