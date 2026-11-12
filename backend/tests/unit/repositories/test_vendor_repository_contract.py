"""VendorRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

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
    """Vendor를 저장한 뒤 읽으면 그대로 돌아오는지 확인한다."""
    # given: Vendor가 있다
    vendor = make_vendor("ZZ SAP", now=NOW)
    # when: 저장하고 다시 읽는다
    await vendor_case.vendors.add(vendor)

    stored = await vendor_case.vendors.get(vendor.id)

    # then: 같은 Vendor이고 이름·생성·수정 시각이 보존된다
    assert stored == vendor
    assert stored.name == "ZZ SAP"
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_get_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    """없는 Vendor를 읽으면 VendorNotFoundError인지 확인한다."""
    # when·then: 없는 id로 읽으면 VendorNotFoundError가 난다
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.get(VendorId(new_id()))


async def test_list_orders_vendors_by_lower_name_then_id(vendor_case: VendorCase) -> None:
    """목록이 소문자 이름 순으로 정렬되는지 확인한다."""
    # given: 대소문자가 섞인 이름의 Vendor 셋을 순서 없이 저장한다
    beta = make_vendor("ZZ beta")
    alpha_upper = make_vendor("ZZ Alpha")
    gamma = make_vendor("ZZ Gamma")
    for vendor in (beta, gamma, alpha_upper):
        await vendor_case.vendors.add(vendor)

    # when: 자기 Vendor만 목록으로 조회한다
    listed = await vendor_case.mine({beta.id, gamma.id, alpha_upper.id})

    # then: 대소문자 무시 이름 순이다
    assert [v.name for v in listed] == ["ZZ Alpha", "ZZ beta", "ZZ Gamma"]


async def test_vendor_names_sort_by_code_point_not_locale(vendor_case: VendorCase) -> None:
    """이름 정렬이 로케일이 아닌 코드 포인트 순인지 확인한다."""
    # given: 한글 이름과 영문 이름 Vendor를 저장한다
    korean = make_vendor("ZZ 가나다")
    latin = make_vendor("ZZ zebra")
    await vendor_case.vendors.add(korean)
    await vendor_case.vendors.add(latin)

    # when: 자기 Vendor만 목록으로 조회한다
    listed = await vendor_case.mine({korean.id, latin.id})

    # then: 영문이 한글보다 먼저다
    assert [v.name for v in listed] == ["ZZ zebra", "ZZ 가나다"]


async def test_duplicate_vendor_name_ignoring_case_raises(vendor_case: VendorCase) -> None:
    """대소문자만 다른 Vendor 이름은 중복인지 확인한다."""
    # given: Vendor를 저장한다
    await vendor_case.vendors.add(make_vendor("ZZ SAP"))

    # when·then: 대소문자만 다른 이름으로 저장하면 DuplicateVendorNameError가 난다
    with pytest.raises(DuplicateVendorNameError):
        await vendor_case.vendors.add(make_vendor("zz sap"))


async def test_renaming_to_another_vendors_name_raises(vendor_case: VendorCase) -> None:
    """다른 Vendor의 이름으로 바꾸면 중복 오류인지 확인한다."""
    # given: Vendor 두 개를 저장하고 둘째 이름을 첫째와 대소문자만 다르게 바꿔 둔다
    first = make_vendor("ZZ One")
    second = make_vendor("ZZ Two")
    await vendor_case.vendors.add(first)
    await vendor_case.vendors.add(second)
    second.rename("zz one", later(1))

    # when·then: 수정 저장하면 DuplicateVendorNameError가 난다
    with pytest.raises(DuplicateVendorNameError):
        await vendor_case.vendors.update(second)


async def test_renaming_a_vendor_to_its_own_name_in_other_case_is_stored(
    vendor_case: VendorCase,
) -> None:
    """자기 이름의 대소문자만 바꾸는 수정이 저장되는지 확인한다."""
    # given: 저장된 Vendor의 이름 대소문자를 바꿔 둔다
    vendor = make_vendor("ZZ Sap")
    await vendor_case.vendors.add(vendor)
    vendor.rename("ZZ SAP", later(1))

    # when: 수정 저장한다
    await vendor_case.vendors.update(vendor)

    # then: 바뀐 이름과 수정 시각이 읽힌다
    stored = await vendor_case.vendors.get(vendor.id)
    assert (stored.name, stored.updated_at) == ("ZZ SAP", later(1))


async def test_update_renames_vendor(vendor_case: VendorCase) -> None:
    """이름 수정이 저장되는지 확인한다."""
    # given: 저장된 Vendor의 이름을 바꿔 둔다
    vendor = make_vendor("ZZ SAP", now=NOW)
    await vendor_case.vendors.add(vendor)
    vendor.rename("ZZ SAP Korea", later(4))

    # when: 수정 저장한다
    await vendor_case.vendors.update(vendor)

    # then: 이름·수정 시각이 바뀌고 생성 시각은 그대로다
    stored = await vendor_case.vendors.get(vendor.id)
    assert (stored.name, stored.created_at, stored.updated_at) == ("ZZ SAP Korea", NOW, later(4))


async def test_update_duplicate_name_raises_duplicate(vendor_case: VendorCase) -> None:
    """중복 이름으로 수정하면 DuplicateVendorNameError인지 확인한다."""
    # given: Vendor 두 개를 저장하고 둘째 이름을 첫째와 대소문자만 다르게 바꿔 둔다
    await vendor_case.vendors.add(make_vendor("ZZ One"))
    second = make_vendor("ZZ Two")
    await vendor_case.vendors.add(second)
    second.rename("ZZ ONE", later(1))

    # when·then: 수정 저장하면 DuplicateVendorNameError가 난다
    with pytest.raises(DuplicateVendorNameError):
        await vendor_case.vendors.update(second)


async def test_update_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    """없는 Vendor를 수정하면 VendorNotFoundError인지 확인한다."""
    # when·then: 저장하지 않은 Vendor를 수정하면 VendorNotFoundError가 난다
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.update(make_vendor("ZZ ghost"))


async def test_delete_vendor_removes_only_that_vendor(vendor_case: VendorCase) -> None:
    """삭제하면 그 Vendor만 사라지는지 확인한다."""
    # given: Vendor 두 개를 저장한다
    vendor = make_vendor("ZZ SAP")
    other = make_vendor("ZZ Oracle")
    await vendor_case.vendors.add(vendor)
    await vendor_case.vendors.add(other)

    # when: 하나를 삭제한다
    await vendor_case.vendors.delete(vendor.id)

    # then: 삭제한 Vendor는 읽으면 VendorNotFoundError고 다른 Vendor는 그대로 남는다
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.get(vendor.id)
    assert [v.id for v in await vendor_case.mine({vendor.id, other.id})] == [other.id]
    assert (await vendor_case.vendors.get(other.id)).name == "ZZ Oracle"


async def test_delete_missing_vendor_raises_not_found(vendor_case: VendorCase) -> None:
    """없는 Vendor를 삭제하면 VendorNotFoundError인지 확인한다."""
    # when·then: 없는 id를 삭제하면 VendorNotFoundError가 난다
    with pytest.raises(VendorNotFoundError):
        await vendor_case.vendors.delete(VendorId(9))


async def test_a_deleted_vendors_name_can_be_used_again(vendor_case: VendorCase) -> None:
    """삭제한 Vendor의 이름을 다시 쓸 수 있는지 확인한다."""
    # given: Vendor를 저장했다가 삭제한다
    vendor = make_vendor("ZZ SAP")
    await vendor_case.vendors.add(vendor)
    await vendor_case.vendors.delete(vendor.id)

    # when·then: 같은 이름으로 다시 저장해도 오류가 나지 않는다
    await vendor_case.vendors.add(make_vendor("ZZ SAP"))
