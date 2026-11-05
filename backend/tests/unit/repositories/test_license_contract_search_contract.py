"""LicenseContractRepository.search·count 필터 계약(AC17·Q1): Fake와 SQL 구현에 같은 테스트.

고객사명·제품명·Vendor·담당영업은 계약이 아니라 Deal 값 기준이다. 조건은 AND이고 count는 같은 조건의
전체 건수다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.license_contract_repository import LicenseContractQuery
from app.domain.license_contract.values import ContractStatus
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.license_contract_case import ContractCase


async def _ids_by_customer(contract_case: ContractCase, **criteria: object) -> list[str]:
    from app.application.ports.license_contract_repository import (  # noqa: PLC0415
        LicenseContractQuery as Query,
    )

    rows = await contract_case.repository.search(Query(limit=200, **criteria))  # type: ignore[arg-type]
    return [r.deal.customer for r in rows]


async def test_search_without_conditions_returns_every_contract(
    contract_case: ContractCase,
) -> None:
    for customer in ("가고객", "나고객"):
        await contract_case.contract(await contract_case.deal(customer=customer))

    assert sorted(await _ids_by_customer(contract_case)) == ["가고객", "나고객"]
    assert await contract_case.total() == 2


async def test_search_customer_is_a_case_insensitive_partial_match_on_the_deal_customer(
    contract_case: ContractCase,
) -> None:
    for customer in ("NextCorp", "네오인", "Other"):
        await contract_case.contract(await contract_case.deal(customer=customer))

    assert await _ids_by_customer(contract_case, customer="next") == ["NextCorp"]
    assert await _ids_by_customer(contract_case, customer="XTCO") == ["NextCorp"]
    assert await _ids_by_customer(contract_case, customer="오인") == ["네오인"]
    assert await contract_case.total(customer="next") == 1


async def test_search_product_is_a_case_insensitive_partial_match_on_the_deal_solution(
    contract_case: ContractCase,
) -> None:
    for solution in ("S/4HANA", "Oracle EBS"):
        deal = await contract_case.deal(solution=solution, customer=solution.replace(" ", ""))
        await contract_case.contract(deal)

    assert await _ids_by_customer(contract_case, product="hana") == ["S/4HANA"]
    assert await _ids_by_customer(contract_case, product="EBS") == ["OracleEBS"]
    assert await contract_case.total(product="hana") == 1


@pytest.mark.parametrize(
    ("needle", "expected"),
    [("100%", ["100%할인"]), ("a_b", ["a_b"]), ("c\\d", ["c\\d"]), ("%", ["100%할인"])],
)
async def test_search_wildcard_characters_are_literal(
    contract_case: ContractCase, needle: str, expected: list[str]
) -> None:
    for customer in ("100%할인", "a_b", "axb", "c\\d", "cd"):
        await contract_case.contract(await contract_case.deal(customer=customer))

    assert await _ids_by_customer(contract_case, customer=needle) == expected


async def test_search_vendor_matches_the_deal_vendor_id(contract_case: ContractCase) -> None:
    sap = await contract_case.deal(customer="SAP사용", vendor="SAP")
    oracle = await contract_case.deal(customer="오라클사용", vendor="Oracle")
    none = await contract_case.deal(customer="벤더없음")
    for deal in (sap, oracle, none):
        await contract_case.contract(deal)

    assert await _ids_by_customer(contract_case, vendor_id=sap.details.vendor_id) == ["SAP사용"]
    assert await contract_case.total(vendor_id=oracle.details.vendor_id) == 1


async def test_search_owner_matches_the_deal_owner_including_resigned_users(
    contract_case: ContractCase,
) -> None:
    kim = await contract_case.deal(customer="김담당", owner="lcs-kim")
    park = await contract_case.deal(customer="박담당", owner="lcs-park")
    for deal in (kim, park):
        await contract_case.contract(deal)
    await contract_case.resign(uid("lcs-park"))

    assert await _ids_by_customer(contract_case, owner_user_id=uid("lcs-kim")) == ["김담당"]
    assert await _ids_by_customer(contract_case, owner_user_id=uid("lcs-park")) == ["박담당"]


@pytest.mark.parametrize("status", list(ContractStatus))
async def test_search_filters_by_status(
    contract_case: ContractCase, status: ContractStatus
) -> None:
    made = {}
    for each in ContractStatus:
        deal = await contract_case.deal()
        made[each] = await contract_case.contract(deal, status=each.value)

    assert await contract_case.row_ids(status=status) == [made[status].id]
    assert await contract_case.total(status=status) == 1


async def test_search_start_range_is_inclusive_and_excludes_contracts_without_dates(
    contract_case: ContractCase,
) -> None:
    starts = {
        "d1": date(2026, 1, 1),
        "d2": date(2026, 2, 1),
        "d3": date(2026, 3, 1),
    }
    made = {}
    for key, day in starts.items():
        made[key] = await contract_case.contract(
            await contract_case.deal(), status="issued_new", start=day
        )
    made["none"] = await contract_case.contract(await contract_case.deal())  # 날짜 없음

    both = await contract_case.row_ids(start_from=date(2026, 2, 1), start_to=date(2026, 3, 1))
    assert sorted(both) == sorted([made["d2"].id, made["d3"].id])
    assert await contract_case.row_ids(start_to=date(2026, 1, 31)) == [made["d1"].id]
    only_from = await contract_case.row_ids(start_from=date(2026, 3, 1))
    assert only_from == [made["d3"].id]
    assert await contract_case.total(start_from=date(2026, 2, 1), start_to=date(2026, 3, 1)) == 2


async def test_search_end_range_is_inclusive_and_excludes_contracts_without_dates(
    contract_case: ContractCase,
) -> None:
    short = await contract_case.contract(
        await contract_case.deal(),
        status="issued_new",
        start=date(2026, 1, 1),
        amount=6,
        unit="month",
    )  # 종료 2026-06-30
    long = await contract_case.contract(
        await contract_case.deal(), status="ended", start=date(2026, 1, 1)
    )  # 종료 2026-12-31
    await contract_case.contract(await contract_case.deal())

    assert await contract_case.row_ids(end_to=date(2026, 6, 30)) == [short.id]
    assert await contract_case.row_ids(end_from=date(2026, 6, 30), end_to=date(2026, 12, 31)) == (
        sorted([short.id, long.id])
    )
    assert await contract_case.row_ids(end_from=date(2026, 7, 1)) == [long.id]
    assert await contract_case.total(end_from=date(2026, 7, 1)) == 1


async def test_search_conditions_are_anded(contract_case: ContractCase) -> None:
    sap = await contract_case.deal(customer="공통고객", vendor="SAP", solution="ERP")
    other_vendor = await contract_case.deal(customer="공통고객", vendor="Oracle", solution="ERP")
    other_customer = await contract_case.deal(customer="다른고객", vendor="SAP", solution="ERP")
    target = await contract_case.contract(sap, status="issued_new")
    await contract_case.contract(other_vendor, status="issued_new")
    await contract_case.contract(other_customer, status="issued_new")
    await contract_case.contract(sap, status="ended")

    found = await contract_case.row_ids(
        customer="공통", vendor_id=sap.details.vendor_id, status=ContractStatus.ISSUED_NEW
    )

    assert found == [target.id]


async def test_search_pages_and_count_is_not_limited_by_the_page(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    made = [await contract_case.contract(deal, status="ended") for _ in range(5)]

    first = await contract_case.repository.search(LicenseContractQuery(limit=2))
    second = await contract_case.repository.search(LicenseContractQuery(offset=2, limit=2))
    last = await contract_case.repository.search(LicenseContractQuery(offset=4, limit=2))

    ids = [r.contract.id for page in (first, second, last) for r in page]
    assert ids == sorted(c.id for c in made)  # 종료일이 같으니 id 오름차순
    assert (len(first), len(second), len(last)) == (2, 2, 1)
    assert await contract_case.total(limit=2) == 5


async def test_search_rows_carry_the_attachment_count(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    with_files = await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    await contract_case.attach(with_files, "a.pdf")
    await contract_case.attach(with_files, "b.pdf")

    rows = await contract_case.repository.search(LicenseContractQuery(limit=200))

    assert {r.contract.id: r.attachment_count for r in rows}[with_files.id] == 2
    assert sorted(r.attachment_count for r in rows) == [0, 2]
