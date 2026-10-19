"""Deal이 Vendor·Solution을 참조하는 계약(AC-6·12·13): Fake와 SQL(PostgreSQL)에 같은 기대값.

- 저장·왕복: `vendor_id`·`solution_id`가 그대로 돌아온다
- 삭제: Deal이 쓰는 Vendor·Solution은 지울 수 없다(건수 포함). 소속 Solution만 써도 Vendor 불가
- 참조: 없는 Vendor, 다른 Vendor의 Solution은 InvalidReferenceError(복합 FK 모사)
- 사용 수: `count_by_vendor`, `count_by_solution`
"""

import dataclasses
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.common.errors import InvalidReferenceError
from app.domain.vendor.errors import SolutionInUseError, VendorInUseError
from app.domain.vendor.values import SolutionId, VendorId
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from app.domain.deal.values import DealDetails
    from tests.unit.repositories.deal_case import DealCase


def _code(n: int) -> str:
    return f"20261016-A{n:03d}"


async def test_deal_round_trips_vendor_and_solution_ids(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA",))
    deal = make_deal(code=_code(1), vendor_id=sap.id, solution_id=sap.solutions[0].id)
    await deal_case.add(deal)

    loaded = await deal_case.deals.get(deal.id)

    assert (loaded.details.vendor_id, loaded.details.solution_id) == (sap.id, sap.solutions[0].id)


async def test_deal_with_vendor_only_round_trips(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA",))
    deal = make_deal(code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)

    loaded = await deal_case.deals.get(deal.id)

    assert (loaded.details.vendor_id, loaded.details.solution_id) == (sap.id, None)


async def test_saving_an_unknown_vendor_is_an_invalid_reference(deal_case: DealCase) -> None:
    deal = make_deal(code=_code(1), vendor_id=VendorId(uuid4()))

    with pytest.raises(InvalidReferenceError):
        await deal_case.add(deal)

    assert await deal_case.deals.exists(deal.id) is False


async def test_saving_a_solution_of_another_vendor_raises_invalid_reference(
    deal_case: DealCase,
) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA",))
    oracle = await deal_case.new_vendor("ZZ Oracle", ("EBS",))
    deal = make_deal(code=_code(1), vendor_id=sap.id, solution_id=oracle.solutions[0].id)

    with pytest.raises(InvalidReferenceError):
        await deal_case.add(deal)

    assert await deal_case.deals.exists(deal.id) is False


async def test_saving_an_unknown_solution_raises_invalid_reference(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA",))
    deal = make_deal(code=_code(1), vendor_id=sap.id, solution_id=SolutionId(uuid4()))

    with pytest.raises(InvalidReferenceError):
        await deal_case.add(deal)


async def test_updating_to_a_solution_of_another_vendor_raises_and_keeps_the_old_choice(
    deal_case: DealCase,
) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA",))
    oracle = await deal_case.new_vendor("ZZ Oracle", ("EBS",))
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id, solution_id=sap.solutions[0].id)
    await deal_case.add(deal)

    with pytest.raises(InvalidReferenceError):
        await deal_case.revise(
            deal.id,
            details=_with(deal, vendor_id=sap.id, solution_id=oracle.solutions[0].id),
        )

    loaded = await deal_case.deals.get(deal.id)
    assert (loaded.details.vendor_id, loaded.details.solution_id) == (sap.id, sap.solutions[0].id)


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


async def test_deleting_a_vendor_whose_solution_is_used_raises_vendor_in_use(
    deal_case: DealCase,
) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA", "BW"))
    await deal_case.add(
        make_deal(later(1), code=_code(1), vendor_id=sap.id, solution_id=sap.solutions[0].id)
    )

    with pytest.raises(VendorInUseError) as raised:
        await deal_case.vendors.delete(sap.id)

    assert raised.value.usage == 1
    assert len((await deal_case.vendors.get(sap.id)).solutions) == 2


async def test_removing_a_solution_used_by_a_deal_raises_in_use(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA", "BW"))
    used = sap.solutions[0]
    await deal_case.add(make_deal(later(1), code=_code(1), vendor_id=sap.id, solution_id=used.id))
    sap.solutions.remove(used)  # 도메인 검사를 건너뛰고 저장소 계약만 확인한다

    with pytest.raises(SolutionInUseError) as raised:
        await deal_case.vendors.update(sap)

    assert raised.value.usage == 1
    assert (await deal_case.vendors.get(sap.id)).has_solution(used.id)


async def test_an_unused_vendor_can_be_deleted_after_its_deals_moved_away(
    deal_case: DealCase,
) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)
    await deal_case.revise(deal.id, details=_with(deal, vendor_id=None, solution_id=None))

    await deal_case.vendors.delete(sap.id)

    assert [v.id for v in await deal_case.vendors.list() if v.id == sap.id] == []


async def test_deleting_a_deal_releases_its_vendor(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)
    await deal_case.deals.delete(deal.id)

    await deal_case.vendors.delete(sap.id)


async def test_count_by_vendor_and_by_solution(deal_case: DealCase) -> None:
    sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA", "BW"))
    oracle = await deal_case.new_vendor("ZZ Oracle", ("EBS",))
    s4, bw = sap.solutions
    await deal_case.add(make_deal(later(1), code=_code(1), vendor_id=sap.id, solution_id=s4.id))
    await deal_case.add(make_deal(later(2), code=_code(2), vendor_id=sap.id, solution_id=s4.id))
    await deal_case.add(make_deal(later(3), code=_code(3), vendor_id=sap.id))
    await deal_case.add(make_deal(later(4), code=_code(4), vendor_id=oracle.id))
    await deal_case.add(make_deal(later(5), code=_code(5)))

    by_vendor = await deal_case.deals.count_by_vendor()
    by_solution = await deal_case.deals.count_by_solution()

    assert {k: v for k, v in by_vendor.items() if v} == {sap.id: 3, oracle.id: 1}
    assert {k: v for k, v in by_solution.items() if v} == {s4.id: 2}
    assert by_solution.get(bw.id, 0) == 0
    assert by_solution.get(oracle.solutions[0].id, 0) == 0


async def test_counts_of_an_empty_repository_are_empty(deal_case: DealCase) -> None:
    assert {k: v for k, v in (await deal_case.deals.count_by_vendor()).items() if v} == {}
    assert {k: v for k, v in (await deal_case.deals.count_by_solution()).items() if v} == {}
