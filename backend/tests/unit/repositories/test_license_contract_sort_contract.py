"""LicenseContractRepository.search 정렬 계약(AC18): 12개 열의 오름/내림, Fake와 SQL 같은 테스트.

주 키 방향대로 정렬하고(텍스트는 대소문자 무시 코드 포인트 순, 상태·점검주기는 업무 순서),
값 없는 칸은 방향과 무관하게 맨 뒤, 동률은 방향과 무관하게 id 오름차순이다.
다섯 계약 A~E(만든 순서 = id 순서)로 열마다 기대 순서를 고정한다.
"""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_repository import SortOrder
from app.application.ports.license_contract_repository import (
    LicenseContractQuery,
    LicenseContractSort,
)

if TYPE_CHECKING:
    from tests.unit.repositories.license_contract_case import ContractCase

# 열마다 (값이 있는 계약의 오름차순 순서, 값 없는 계약). 동률은 id 오름차순(A<B<C<D<E).
#   deal_name  A Gamma  B alpha  C delta  D Beta  E echo (대소문자 무시)
#   customer   A bravo  B Alpha  C charlie  D Delta  E echo
#   vendor     A SAP    B Oracle C Zebra    D Microsoft E adobe (Vendor는 필수라 모두 있다)
#   product    A S4     B ''     C ERP      D crm    E Zeta
#   partner    A hanbit B -      C Anchor   D beta   E -
#   start      A 03-01  B 01-01  C -        D 2025-06-01  E 03-01
#   end        A 2027-02-28 B 2026-12-31 C - D 2026-05-31 E 2026-08-31
#   status     A issued_new B ended C not_issued D issued_renewal E issued_new
#   owner      A kim(Kim) B park(Park) C lee(display 없음) D choi(Choi) E ann(Ann)
#   tech       A zed B '' C Amy D bob E Bob
#   inspection A yearly B none C monthly D quarterly E semiannual
#   note       A n-b B '' C alpha note D Zulu E alpha note
ASC = {
    "deal_name": ("BDCEA", ""),
    "customer": ("BACDE", ""),
    "vendor": ("EDBAC", ""),
    "product": ("DCAE", "B"),
    "partner": ("CDA", "BE"),
    "license_start": ("DBAE", "C"),
    "license_end": ("DEBA", "C"),
    "status": ("CAEDB", ""),
    "sales_owner": ("EDACB", ""),
    "tech_owner": ("CDEA", "B"),
    "inspection": ("CDEAB", ""),
    "note": ("CEAD", "B"),
}
# 내림차순: 값이 있는 쪽을 뒤집되 동률은 id 오름차순을 유지한다.
DESC = {
    "deal_name": ("AECDB", ""),
    "customer": ("EDCAB", ""),
    "vendor": ("CABDE", ""),
    "product": ("EACD", "B"),
    "partner": ("ADC", "BE"),
    "license_start": ("AEBD", "C"),
    "license_end": ("ABED", "C"),
    "status": ("BDAEC", ""),
    "sales_owner": ("BCADE", ""),
    "tech_owner": ("ADEC", "B"),
    "inspection": ("BAEDC", ""),
    "note": ("DACE", "B"),
}


async def _seed(contract_case: ContractCase) -> dict[str, int]:
    rows = [
        ("A", "bravo", "SAP", "S4", "hanbit", "kim", "Kim"),
        ("B", "Alpha", "Oracle", "", None, "park", "Park"),
        ("C", "charlie", "Zebra", "ERP", "Anchor", "lee", None),
        ("D", "Delta", "Microsoft", "crm", "beta", "choi", "Choi"),
        ("E", "echo", "adobe", "Zeta", None, "ann", "Ann"),
    ]
    contracts: dict[str, dict[str, Any]] = {
        "A": {
            "status": "issued_new",
            "start": date(2026, 3, 1),
            "tech_owner": "zed",
            "inspection": "yearly",
            "note": "n-b",
        },
        "B": {
            "status": "ended",
            "start": date(2026, 1, 1),
            "tech_owner": "",
            "inspection": "none",
            "note": "",
        },
        "C": {
            "status": "not_issued",
            "tech_owner": "Amy",
            "inspection": "monthly",
            "note": "alpha note",
        },
        "D": {
            "status": "issued_renewal",
            "start": date(2025, 6, 1),
            "tech_owner": "bob",
            "inspection": "quarterly",
            "note": "Zulu",
        },
        "E": {
            "status": "issued_new",
            "start": date(2026, 3, 1),
            "amount": 6,
            "unit": "month",
            "tech_owner": "Bob",
            "inspection": "semiannual",
            "note": "alpha note",
        },
    }
    deal_names = {"A": "Gamma", "B": "alpha", "C": "delta", "D": "Beta", "E": "echo"}
    ids: dict[str, int] = {}
    for key, customer, vendor, product, partner, owner, display in rows:
        deal = await contract_case.deal(
            customer=customer,
            vendor=vendor,
            product=product,
            partner=partner,
            owner=owner,
            owner_display=display,
            name=deal_names[key],
        )
        made = await contract_case.contract(deal, **contracts[key])
        ids[key] = made.id
    return ids


def _expected(spec: tuple[str, str], ids: dict[str, int]) -> list[int]:
    present, absent = spec
    return [ids[k] for k in present] + [ids[k] for k in absent]


@pytest.mark.parametrize("sort", [LicenseContractSort(key) for key in ASC])
async def test_search_sort_each_column_asc_empty_last_tie_by_id(
    contract_case: ContractCase, sort: LicenseContractSort
) -> None:
    """12개 열 각각 오름차순이고 값 없는 계약은 맨 뒤, 동률은 id 순이다.

    테스트 코드: LC-021
    """
    # given: 열마다 값이 다른 계약 A~E
    ids = await _seed(contract_case)

    # when: 열을 오름차순으로 정렬해 검색한다
    found = await contract_case.row_ids(sort=sort, order=SortOrder.ASC)

    # then: 기대한 순서와 같다
    assert found == _expected(ASC[sort.value], ids)


@pytest.mark.parametrize("sort", [LicenseContractSort(key) for key in ASC])
async def test_search_sort_each_column_desc_empty_last_tie_by_id(
    contract_case: ContractCase, sort: LicenseContractSort
) -> None:
    """12개 열 각각 내림차순이어도 값 없는 계약은 맨 뒤, 동률은 id 오름차순이다.

    테스트 코드: LC-021
    """
    # given: 열마다 값이 다른 계약 A~E
    ids = await _seed(contract_case)

    # when: 열을 내림차순으로 정렬해 검색한다
    found = await contract_case.row_ids(sort=sort, order=SortOrder.DESC)

    # then: 기대한 순서와 같다
    assert found == _expected(DESC[sort.value], ids)


async def test_the_default_sort_is_license_end_ascending(contract_case: ContractCase) -> None:
    """정렬을 주지 않으면 종료일 오름차순이다.

    테스트 코드: LC-016
    """
    # given: 열마다 값이 다른 계약 A~E
    ids = await _seed(contract_case)

    # when: 정렬 없이 검색한다
    rows = await contract_case.repository.search(LicenseContractQuery(limit=200))

    # then: 종료일 오름차순이고 종료일 없는 계약이 맨 뒤다
    assert [r.contract.id for r in rows] == _expected(ASC["license_end"], ids)


async def test_paging_keeps_the_sorted_order_across_pages(contract_case: ContractCase) -> None:
    """쪽을 나눠 읽어도 정렬 순서가 이어진다.

    테스트 코드: LC-016, LC-021
    """
    # given: 열마다 값이 다른 계약 A~E
    ids = await _seed(contract_case)
    query: dict[str, Any] = {"sort": LicenseContractSort.CUSTOMER, "order": SortOrder.ASC}

    # when: 고객사명 오름차순으로 두 쪽을 읽는다
    first = await contract_case.repository.search(LicenseContractQuery(limit=2, **query))
    second = await contract_case.repository.search(LicenseContractQuery(offset=2, limit=3, **query))

    # then: 이어 붙인 순서가 한 번에 읽은 순서와 같다
    paged = [r.contract.id for r in (*first, *second)]
    assert paged == _expected(ASC["customer"], ids)


def test_deal_name_is_an_accepted_sort_column() -> None:
    """deal_name은 허용된 정렬 키다.

    테스트 코드: LC-084
    """
    # when: LicenseContractSort('deal_name')을 만든다
    value = LicenseContractSort("deal_name").value
    # then: 값이 deal_name이다
    assert value == "deal_name"
