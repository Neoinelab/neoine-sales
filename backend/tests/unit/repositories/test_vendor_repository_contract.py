"""VendorRepository 계약(AC-1·3·4): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

이름은 다른 테스트의 행과 겹치지 않는 `ZZ ` 접두를 쓰고, 목록은 `mine`으로 자기 행만 비교한다.
정렬 계약: `lower(name)` 코드 포인트 순, 동률은 id 순. Deal 사용 중 삭제 계약은
`test_deal_vendor_reference_contract.py`다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.vendor.errors import (
    DuplicateVendorNameError,
    VendorNotFoundError,
)
from app.domain.vendor.values import VendorId
from tests.factories import NOW, later
from tests.factories_vendor import make_vendor
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.vendor_case import VendorCase


async def test_add_then_get_round_trips_a_vendor(vendor_case: VendorCase) -> None:
    vendor = make_vendor("ZZ SAP", now=NOW)
    await vendor_case.vendors.add(vendor)

    stored = await vendor_case.vendors.get(vendor.id)

    assert stored == vendor
    assert stored.name == "ZZ SAP"
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_get_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.get(VendorId(new_id()))


async def test_list_orders_vendors_by_lower_name_then_id(vendor_case: VendorCase) -> None:
    beta = make_vendor("ZZ beta")
    alpha_upper = make_vendor("ZZ Alpha")
    gamma = make_vendor("ZZ Gamma")
    for vendor in (beta, gamma, alpha_upper):
        await vendor_case.vendors.add(vendor)

    listed = await vendor_case.mine({beta.id, gamma.id, alpha_upper.id})

    assert [v.name for v in listed] == ["ZZ Alpha", "ZZ beta", "ZZ Gamma"]


async def test_vendor_names_sort_by_code_point_not_locale(vendor_case: VendorCase) -> None:
    korean = make_vendor("ZZ 가나다")
    latin = make_vendor("ZZ zebra")
    await vendor_case.vendors.add(korean)
    await vendor_case.vendors.add(latin)

    listed = await vendor_case.mine({korean.id, latin.id})

    assert [v.name for v in listed] == ["ZZ zebra", "ZZ 가나다"]


async def test_duplicate_vendor_name_ignoring_case_raises(vendor_case: VendorCase) -> None:
    await vendor_case.vendors.add(make_vendor("ZZ SAP"))

    with pytest.raises(DuplicateVendorNameError):
        await vendor_case.vendors.add(make_vendor("zz sap"))


async def test_renaming_to_another_vendors_name_raises(vendor_case: VendorCase) -> None:
    first = make_vendor("ZZ One")
    second = make_vendor("ZZ Two")
    await vendor_case.vendors.add(first)
    await vendor_case.vendors.add(second)
    second.rename("zz one", later(1))

    with pytest.raises(DuplicateVendorNameError):
        await vendor_case.vendors.update(second)


async def test_renaming_a_vendor_to_its_own_name_in_other_case_is_stored(
    vendor_case: VendorCase,
) -> None:
    vendor = make_vendor("ZZ Sap")
    await vendor_case.vendors.add(vendor)
    vendor.rename("ZZ SAP", later(1))

    await vendor_case.vendors.update(vendor)

    stored = await vendor_case.vendors.get(vendor.id)
    assert (stored.name, stored.updated_at) == ("ZZ SAP", later(1))


async def test_update_renames_vendor(vendor_case: VendorCase) -> None:
    vendor = make_vendor("ZZ SAP", now=NOW)
    await vendor_case.vendors.add(vendor)
    vendor.rename("ZZ SAP Korea", later(4))

    await vendor_case.vendors.update(vendor)

    stored = await vendor_case.vendors.get(vendor.id)
    assert (stored.name, stored.created_at, stored.updated_at) == ("ZZ SAP Korea", NOW, later(4))


async def test_update_duplicate_name_raises_duplicate(vendor_case: VendorCase) -> None:
    await vendor_case.vendors.add(make_vendor("ZZ One"))
    second = make_vendor("ZZ Two")
    await vendor_case.vendors.add(second)
    second.rename("ZZ ONE", later(1))

    with pytest.raises(DuplicateVendorNameError):
        await vendor_case.vendors.update(second)


async def test_update_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.update(make_vendor("ZZ ghost"))


async def test_delete_vendor_removes_only_that_vendor(vendor_case: VendorCase) -> None:
    vendor = make_vendor("ZZ SAP")
    other = make_vendor("ZZ Oracle")
    await vendor_case.vendors.add(vendor)
    await vendor_case.vendors.add(other)

    await vendor_case.vendors.delete(vendor.id)

    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.get(vendor.id)
    assert [v.id for v in await vendor_case.mine({vendor.id, other.id})] == [other.id]
    assert (await vendor_case.vendors.get(other.id)).name == "ZZ Oracle"


async def test_delete_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.delete(VendorId(9))


async def test_a_deleted_vendors_name_can_be_used_again(vendor_case: VendorCase) -> None:
    vendor = make_vendor("ZZ SAP")
    await vendor_case.vendors.add(vendor)
    await vendor_case.vendors.delete(vendor.id)

    await vendor_case.vendors.add(make_vendor("ZZ SAP"))
