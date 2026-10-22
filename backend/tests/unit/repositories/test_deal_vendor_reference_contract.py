"""Deal이 Vendor를 참조하는 계약(AC-3·4): Fake와 SQL(PostgreSQL)에 같은 기대값.

- 저장·왕복: `vendor_id`가 그대로 돌아오고, Solution 텍스트는 Vendor와 독립이다
- 삭제: Deal이 쓰는 Vendor는 지울 수 없다(건수 포함)
- 참조: 없는 Vendor는 InvalidReferenceError(Solution은 자유 텍스트라 참조 검사 없음)
- 사용 수: `count_by_vendor`
"""

import dataclasses
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidReferenceError
from app.domain.vendor.errors import VendorInUseError
from app.domain.vendor.values import VendorId
from tests.factories import later, make_deal
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from app.domain.deal.values import DealDetails
    from tests.unit.repositories.deal_case import DealCase


def _code(n: int) -> str:
    return f"20261016-A{n:03d}"


async def test_deal_round_trips_vendor_id_and_solution_text(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(code=_code(1), vendor_id=sap.id, solution="S/4HANA")
    await deal_case.add(deal)

    loaded = await deal_case.deals.get(deal.id)

    assert (loaded.details.vendor_id, loaded.details.solution) == (sap.id, "S/4HANA")


async def test_deal_with_vendor_only_round_trips(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)

    loaded = await deal_case.deals.get(deal.id)

    assert (loaded.details.vendor_id, loaded.details.solution) == (sap.id, "S/4HANA")


async def test_saving_an_unknown_vendor_is_an_invalid_reference(deal_case: DealCase) -> None:
    deal = make_deal(code=_code(1), vendor_id=VendorId(new_id()))

    with pytest.raises(InvalidReferenceError):
        await deal_case.add(deal)

    assert await deal_case.deals.exists(deal.id) is False


async def test_unknown_vendor_id_is_rejected_even_with_a_solution_text(
    deal_case: DealCase,
) -> None:
    deal = make_deal(code=_code(1), vendor_id=VendorId(new_id()), solution="ITDR")

    with pytest.raises(InvalidReferenceError):
        await deal_case.add(deal)


async def test_updating_the_vendor_keeps_the_solution_text(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    oracle = await deal_case.new_vendor("ZZ Oracle")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id, solution="ITDR")
    await deal_case.add(deal)

    await deal_case.revise(deal.id, details=_with(deal, vendor_id=oracle.id))

    loaded = await deal_case.deals.get(deal.id)
    assert (loaded.details.vendor_id, loaded.details.solution) == (oracle.id, "ITDR")


def _with(deal: Deal, **fields: object) -> DealDetails:
    return dataclasses.replace(deal.details, **fields)  # type: ignore[arg-type]


async def test_deleting_a_vendor_used_by_a_deal_raises_in_use_with_count(
    deal_case: DealCase,
) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    for n in (1, 2):
        await deal_case.add(make_deal(later(n), code=_code(n), vendor_id=sap.id))

    with pytest.raises(VendorInUseError) as raised:
        await deal_case.vendors.delete(sap.id)

    assert raised.value.usage == 2
    assert (await deal_case.vendors.get(sap.id)).name == "ZZ SAP"


async def test_an_unused_vendor_can_be_deleted_after_its_deals_moved_away(
    deal_case: DealCase,
) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)
    await deal_case.revise(deal.id, details=_with(deal, vendor_id=None))

    await deal_case.vendors.delete(sap.id)

    assert [v.id for v in await deal_case.vendors.list() if v.id == sap.id] == []


async def test_deleting_a_deal_releases_its_vendor(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)
    await deal_case.deals.delete(deal.id)

    await deal_case.vendors.delete(sap.id)


async def test_count_by_vendor(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    oracle = await deal_case.new_vendor("ZZ Oracle")
    await deal_case.add(make_deal(later(1), code=_code(1), vendor_id=sap.id, solution="ITDR"))
    await deal_case.add(make_deal(later(2), code=_code(2), vendor_id=sap.id, solution="ITDR"))
    await deal_case.add(make_deal(later(3), code=_code(3), vendor_id=sap.id))
    await deal_case.add(make_deal(later(4), code=_code(4), vendor_id=oracle.id))
    await deal_case.add(make_deal(later(5), code=_code(5)))

    by_vendor = await deal_case.deals.count_by_vendor()

    assert {k: v for k, v in by_vendor.items() if v} == {sap.id: 3, oracle.id: 1}


async def test_counts_of_an_empty_repository_are_empty(deal_case: DealCase) -> None:
    assert {k: v for k, v in (await deal_case.deals.count_by_vendor()).items() if v} == {}


async def test_count_by_solution_is_gone_from_the_port(deal_case: DealCase) -> None:
    assert not hasattr(deal_case.deals, "count_by_solution")
