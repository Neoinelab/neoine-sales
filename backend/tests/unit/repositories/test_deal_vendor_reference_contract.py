"""Deal이 Vendor를 참조하는 계약: Fake와 SQL(PostgreSQL)에 같은 기대값.

- 저장·왕복: `vendor_id`가 그대로 돌아오고, Product 텍스트는 Vendor와 독립이다
- 삭제: Deal이 쓰는 Vendor는 지울 수 없다(건수 포함)
- 참조: 없는 Vendor는 InvalidReferenceError(Product는 자유 텍스트라 참조 검사 없음)
- 사용 수: `count_by_vendor`
"""

import dataclasses
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidReferenceError
from app.domain.vendor.errors import VendorInUseError
from app.domain.vendor.values import VendorId
from tests.factories import later, make_deal
from tests.support.default_vendor import DEFAULT_VENDOR_ID
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from app.domain.deal.values import DealDetails
    from tests.unit.repositories.deal_case import DealCase


def _code(n: int) -> str:
    return f"20261016-A{n:03d}"


async def test_deal_round_trips_vendor_id_and_product_text(deal_case: DealCase) -> None:
    """Deal의 vendor_id와 Product 텍스트가 저장 뒤 그대로 읽히는지 확인한다."""
    # given: Vendor와 이를 쓰는 Product 텍스트 Deal이 있다
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(code=_code(1), vendor_id=sap.id, product="S/4HANA")
    # when: Deal을 저장하고 다시 읽는다
    await deal_case.add(deal)

    loaded = await deal_case.deals.get(deal.id)

    # then: vendor_id와 Product가 저장한 값이다
    assert (loaded.details.vendor_id, loaded.details.product) == (sap.id, "S/4HANA")


async def test_deal_with_vendor_only_round_trips(deal_case: DealCase) -> None:
    """Vendor만 지정한 Deal이 저장 뒤 그대로 읽히는지 확인한다."""
    # given: Vendor를 쓰고 Product는 기본값인 Deal이 있다
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(code=_code(1), vendor_id=sap.id)
    # when: Deal을 저장하고 다시 읽는다
    await deal_case.add(deal)

    loaded = await deal_case.deals.get(deal.id)

    # then: vendor_id와 기본 Product가 유지된다
    assert (loaded.details.vendor_id, loaded.details.product) == (sap.id, "S/4HANA")


async def test_saving_an_unknown_vendor_is_an_invalid_reference(deal_case: DealCase) -> None:
    """없는 Vendor를 가리키는 Deal 저장이 InvalidReferenceError인지 확인한다."""
    # given: 존재하지 않는 Vendor를 가리키는 Deal이 있다
    deal = make_deal(code=_code(1), vendor_id=VendorId(new_id()))

    # when: Deal을 저장한다
    with pytest.raises(InvalidReferenceError):
        await deal_case.add(deal)

    # when: 저장 여부를 조회한다
    exists = await deal_case.deals.exists(deal.id)

    # then: Deal이 저장되지 않았다
    assert exists is False


async def test_unknown_vendor_id_is_rejected_even_with_a_product_text(
    deal_case: DealCase,
) -> None:
    """Product 텍스트가 있어도 없는 Vendor는 거절하는지 확인한다."""
    # given: 없는 Vendor와 Product 텍스트를 가진 Deal이 있다
    deal = make_deal(code=_code(1), vendor_id=VendorId(new_id()), product="ITDR")

    # when·then: Deal을 저장하면 InvalidReferenceError가 난다
    with pytest.raises(InvalidReferenceError):
        await deal_case.add(deal)


async def test_updating_the_vendor_keeps_the_product_text(deal_case: DealCase) -> None:
    """Vendor를 바꿔 수정해도 Product 텍스트가 유지되는지 확인한다."""
    # given: Vendor와 Product 텍스트가 있는 Deal이 저장되어 있다
    sap = await deal_case.new_vendor("ZZ SAP")
    oracle = await deal_case.new_vendor("ZZ Oracle")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id, product="ITDR")
    await deal_case.add(deal)

    # when: 다른 Vendor로 Deal을 수정한다
    await deal_case.revise(deal.id, details=_with(deal, vendor_id=oracle.id))

    # then: Vendor는 바뀌고 Product는 그대로다
    loaded = await deal_case.deals.get(deal.id)
    assert (loaded.details.vendor_id, loaded.details.product) == (oracle.id, "ITDR")


def _with(deal: Deal, **fields: object) -> DealDetails:
    return dataclasses.replace(deal.details, **fields)  # type: ignore[arg-type]


async def test_deleting_a_vendor_used_by_a_deal_raises_in_use_with_count(
    deal_case: DealCase,
) -> None:
    """Deal이 쓰는 Vendor 삭제가 사용 건수와 함께 VendorInUseError인지 확인한다."""
    # given: Deal 두 개가 쓰는 Vendor가 있다
    sap = await deal_case.new_vendor("ZZ SAP")
    for n in (1, 2):
        await deal_case.add(make_deal(later(n), code=_code(n), vendor_id=sap.id))

    # when: Vendor를 삭제한다
    with pytest.raises(VendorInUseError) as raised:
        await deal_case.vendors.delete(sap.id)

    # then: 사용 건수 2의 VendorInUseError가 나고 Vendor는 그대로 남는다
    assert raised.value.usage == 2
    assert (await deal_case.vendors.get(sap.id)).name == "ZZ SAP"


async def test_an_unused_vendor_can_be_deleted_after_its_deals_moved_away(
    deal_case: DealCase,
) -> None:
    """Deal이 Vendor를 떠나면 그 Vendor를 삭제할 수 있는지 확인한다."""
    # given: Vendor를 쓰던 Deal이 다른 Vendor로 수정되었다
    sap = await deal_case.new_vendor("ZZ SAP")
    oracle = await deal_case.new_vendor("ZZ Oracle")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)
    await deal_case.revise(deal.id, details=_with(deal, vendor_id=oracle.id))

    # when: Vendor를 삭제한다
    await deal_case.vendors.delete(sap.id)

    # then: 목록에 그 Vendor가 없다
    assert [v.id for v in await deal_case.vendors.list() if v.id == sap.id] == []


async def test_deleting_a_deal_releases_its_vendor(deal_case: DealCase) -> None:
    """Deal을 삭제하면 Vendor 삭제가 가능해지는지 확인한다."""
    # given: Vendor를 쓰던 Deal을 저장했다가 삭제한다
    sap = await deal_case.new_vendor("ZZ SAP")
    deal = make_deal(later(1), code=_code(1), vendor_id=sap.id)
    await deal_case.add(deal)
    await deal_case.deals.delete(deal.id)

    # when·then: Vendor를 삭제해도 오류가 나지 않는다
    await deal_case.vendors.delete(sap.id)


async def test_count_by_vendor(deal_case: DealCase) -> None:
    """Vendor별 Deal 사용 수를 세는지 확인한다."""
    # given: 두 Vendor와 그 Vendor를 쓰는 Deal 네 개, 기본 Vendor를 쓰는 Deal 하나가 있다
    sap = await deal_case.new_vendor("ZZ SAP")
    oracle = await deal_case.new_vendor("ZZ Oracle")
    await deal_case.add(make_deal(later(1), code=_code(1), vendor_id=sap.id, product="ITDR"))
    await deal_case.add(make_deal(later(2), code=_code(2), vendor_id=sap.id, product="ITDR"))
    await deal_case.add(make_deal(later(3), code=_code(3), vendor_id=sap.id))
    await deal_case.add(make_deal(later(4), code=_code(4), vendor_id=oracle.id))
    await deal_case.add(make_deal(later(5), code=_code(5)))

    # when: Vendor별 사용 수를 센다
    by_vendor = await deal_case.deals.count_by_vendor()

    # then: 0이 아닌 수가 SAP 3, Oracle 1, 기본 Vendor 1이다
    assert {k: v for k, v in by_vendor.items() if v} == {
        sap.id: 3,
        oracle.id: 1,
        DEFAULT_VENDOR_ID: 1,
    }


async def test_counts_of_an_empty_repository_are_empty(deal_case: DealCase) -> None:
    """Deal이 없으면 Vendor 사용 수가 비어 있는지 확인한다."""
    # when: Vendor별 사용 수를 센다
    counts = await deal_case.deals.count_by_vendor()

    # then: 0이 아닌 수가 없다
    assert {k: v for k, v in counts.items() if v} == {}


async def test_count_by_solution_is_gone_from_the_port(deal_case: DealCase) -> None:
    """Product별 사용 수 메서드가 Port에서 제거되었는지 확인한다."""
    # when·then: 저장소에 count_by_solution이 없다
    assert not hasattr(deal_case.deals, "count_by_solution")
