"""Vendor 삭제 유스케이스: Deal이 쓰면 409 계열, 안 쓰면 삭제. 없는 id는 404 계열."""

from typing import TYPE_CHECKING

import pytest

from app.application.vendor.delete_vendor import DeleteVendor
from app.application.vendor.list_vendors import ListVendors
from app.domain.vendor.errors import VendorInUseError, VendorNotFoundError
from app.domain.vendor.values import VendorId
from tests.factories_deal import SALES, seed_deal
from tests.factories_vendor import make_vendor
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork
    from tests.unit.application.deal_env import DealEnv


async def test_delete_used_vendor_is_rejected_with_count(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Deal이 고른 Vendor를 지우면 실제 Deal 수가 든 오류이고 Vendor는 남는다.

    테스트 코드: CL-060
    """
    # given: SAP를 Deal 2건이 고른다(Solution 텍스트 포함)
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id)
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id, solution="ITDR")

    # when: SAP를 삭제한다
    with pytest.raises(VendorInUseError) as raised:
        await DeleteVendor(uow_factory).execute(sap.id)

    # then: '(Deal 2건)' 오류이고 Vendor는 그대로다
    assert str(raised.value) == "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)"
    assert (await uow.vendors.get(sap.id)).name == "SAP"


async def test_delete_unused_vendor_removes_it(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """쓰이지 않는 Vendor는 삭제되고 커밋된다.

    테스트 코드: CL-059
    """
    # given: SAP·Oracle Vendor가 있고 쓰는 Deal은 없다
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    # when: SAP를 삭제한다
    await DeleteVendor(uow_factory).execute(sap.id)

    # then: Oracle만 남고 커밋 1회다
    assert [v.name for v in await uow.vendors.list()] == ["Oracle"]
    assert uow.commits == 1


async def test_delete_vendor_ignores_usage_of_other_vendors(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """다른 Vendor의 사용은 삭제 판정에 영향을 주지 않는다.

    테스트 코드: CL-059
    """
    # given: Oracle만 Deal이 고른다
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)
    await seed_deal(uow, code="20261016-A001", vendor_id=oracle.id)

    # when: SAP를 삭제한다
    await DeleteVendor(uow_factory).execute(sap.id)

    # then: SAP만 사라지고 Oracle은 남는다
    assert [v.name for v in await uow.vendors.list()] == ["Oracle"]


async def test_vendor_becomes_deletable_after_the_deals_that_chose_it_are_deleted(
    env: DealEnv,
) -> None:
    """Vendor를 고르던 Deal이 모두 지워지면 Vendor를 삭제할 수 있다.

    테스트 코드: CL-061
    """
    # given: SAP를 고른 Deal을 등록했다가 삭제했다
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id)
    code = view.item.deal.id.value
    await env.delete.execute(code, code, SALES)

    # when: SAP를 삭제한다
    await DeleteVendor(env.uow_factory).execute(sap.id)

    # then: Vendor 목록이 비었다
    assert await ListVendors(env.uow_factory).execute() == []


async def test_delete_missing_vendor_raises_not_found(uow_factory: UnitOfWorkFactory) -> None:
    """없는 Vendor를 삭제하면 찾을 수 없음 오류다.

    테스트 코드: CL-057
    """
    # when·then: 없는 id를 삭제한다 → Vendor를 찾을 수 없음 오류다
    with pytest.raises(VendorNotFoundError):
        await DeleteVendor(uow_factory).execute(VendorId(new_id()))


async def test_solution_use_cases_are_gone() -> None:
    """Solution 관리 유스케이스 모듈은 더 이상 없다.

    테스트 코드: CL-062
    """
    import importlib  # noqa: PLC0415

    for module in ("register_solution", "rename_solution", "delete_solution"):
        # when·then: Solution 유스케이스 모듈을 가져온다 → 모듈이 없음 오류다
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(f"app.application.vendor.{module}")
