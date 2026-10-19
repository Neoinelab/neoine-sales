"""VendorRepository 계약(AC-1·3·5·6): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

이름은 다른 테스트의 행과 겹치지 않는 `ZZ ` 접두를 쓰고, 목록은 `mine`으로 자기 행만 비교한다.
정렬 계약: `lower(name)` 코드 포인트 순, 동률은 id 순. Solution도 같다. Deal 사용 중 삭제 계약은
`test_deal_vendor_reference_contract.py`다.
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from app.domain.vendor.errors import (
    DuplicateSolutionNameError,
    DuplicateVendorNameError,
    VendorNotFoundError,
)
from app.domain.vendor.values import VendorId
from tests.factories import NOW, later
from tests.factories_vendor import make_solution, make_vendor, store_vendor

if TYPE_CHECKING:
    from tests.unit.repositories.vendor_case import VendorCase


async def test_add_then_get_round_trips_a_vendor_without_solutions(vendor_case: VendorCase) -> None:
    vendor = make_vendor("ZZ SAP", now=NOW)
    await vendor_case.vendors.add(vendor)

    stored = await vendor_case.vendors.get(vendor.id)

    assert stored == vendor
    assert (stored.name, stored.solutions) == ("ZZ SAP", [])
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_update_adds_solutions_and_get_round_trips_them(vendor_case: VendorCase) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["S/4HANA", "BW"], now=NOW)

    stored = await vendor_case.vendors.get(vendor.id)

    assert sorted((s.name, s.id) for s in stored.solutions) == sorted(
        (s.name, s.id) for s in vendor.solutions
    )
    assert all((s.created_at, s.updated_at) == (NOW, NOW) for s in stored.solutions)


async def test_get_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.get(VendorId(uuid4()))


async def test_list_orders_vendors_by_lower_name_then_id(vendor_case: VendorCase) -> None:
    beta = make_vendor("ZZ beta")
    alpha_upper = make_vendor("ZZ Alpha")
    gamma = make_vendor("ZZ Gamma")
    for vendor in (beta, gamma, alpha_upper):
        await vendor_case.vendors.add(vendor)

    listed = await vendor_case.mine({beta.id, gamma.id, alpha_upper.id})

    assert [v.name for v in listed] == ["ZZ Alpha", "ZZ beta", "ZZ Gamma"]


async def test_list_orders_solutions_by_lower_name_then_id(vendor_case: VendorCase) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["zeta", "Alpha", "beta"])

    (listed,) = await vendor_case.mine({vendor.id})

    assert [s.name for s in listed.solutions] == ["Alpha", "beta", "zeta"]


async def test_get_orders_solutions_the_same_way(vendor_case: VendorCase) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["zeta", "Alpha"])

    stored = await vendor_case.vendors.get(vendor.id)

    assert [s.name for s in stored.solutions] == ["Alpha", "zeta"]


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


async def test_duplicate_solution_name_in_same_vendor_raises(vendor_case: VendorCase) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["Cloud"])
    vendor.solutions.append(make_solution("cloud"))

    with pytest.raises(DuplicateSolutionNameError):
        await vendor_case.vendors.update(vendor)


async def test_duplicate_solution_name_error_identifies_the_solution_name(
    vendor_case: VendorCase,
) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["Cloud"])
    vendor.solutions.append(make_solution("cloud"))

    with pytest.raises(DuplicateSolutionNameError) as raised:
        await vendor_case.vendors.update(vendor)

    assert str(raised.value.identifier).lower() == "cloud"


async def test_same_solution_name_in_two_vendors_is_allowed(vendor_case: VendorCase) -> None:
    first = await store_vendor(vendor_case.vendors, "ZZ One", ["Cloud"])
    second = await store_vendor(vendor_case.vendors, "ZZ Two", ["Cloud"])

    assert [s.name for s in (await vendor_case.vendors.get(first.id)).solutions] == ["Cloud"]
    assert [s.name for s in (await vendor_case.vendors.get(second.id)).solutions] == ["Cloud"]


async def test_update_renames_a_solution_in_place(vendor_case: VendorCase) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["Cloud"])
    solution_id = vendor.solutions[0].id
    vendor.rename_solution(solution_id, "Cloud Edition", later(3))

    await vendor_case.vendors.update(vendor)

    stored = (await vendor_case.vendors.get(vendor.id)).solution(solution_id)
    assert (stored.name, stored.updated_at) == ("Cloud Edition", later(3))


async def test_update_renames_a_solution_to_a_case_variant_of_its_own_name(
    vendor_case: VendorCase,
) -> None:
    """대소문자만 바꾼 Solution 이름 변경도 중복 없이 한 번의 update로 저장된다."""
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["Cloud"])
    vendor.rename_solution(vendor.solutions[0].id, "CLOUD", later(1))

    await vendor_case.vendors.update(vendor)

    assert [s.name for s in (await vendor_case.vendors.get(vendor.id)).solutions] == ["CLOUD"]


async def test_update_removes_dropped_solutions(vendor_case: VendorCase) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["Cloud", "ERP"])
    vendor.remove_solution(vendor.solutions[0].id, usage=0)

    await vendor_case.vendors.update(vendor)

    stored = await vendor_case.vendors.get(vendor.id)
    assert [s.id for s in stored.solutions] == [s.id for s in vendor.solutions]
    assert len(stored.solutions) == 1


async def test_update_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.update(make_vendor("ZZ ghost"))


async def test_delete_vendor_removes_its_solutions(vendor_case: VendorCase) -> None:
    vendor = await store_vendor(vendor_case.vendors, "ZZ SAP", ["Cloud", "ERP"])
    other = await store_vendor(vendor_case.vendors, "ZZ Oracle", ["Cloud"])

    await vendor_case.vendors.delete(vendor.id)

    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.get(vendor.id)
    assert [v.id for v in await vendor_case.mine({vendor.id, other.id})] == [other.id]
    assert len((await vendor_case.vendors.get(other.id)).solutions) == 1


async def test_delete_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.delete(VendorId(UUID(int=9)))


async def test_a_deleted_vendors_name_can_be_used_again(vendor_case: VendorCase) -> None:
    vendor = make_vendor("ZZ SAP")
    await vendor_case.vendors.add(vendor)
    await vendor_case.vendors.delete(vendor.id)

    await vendor_case.vendors.add(make_vendor("ZZ SAP"))
