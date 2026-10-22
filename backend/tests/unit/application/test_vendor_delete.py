"""Vendor 삭제 유스케이스(AC-4): Deal이 쓰면 409 계열, 안 쓰면 삭제. 없는 id는 404 계열."""

from typing import TYPE_CHECKING

import pytest

from app.application.vendor.delete_vendor import DeleteVendor
from app.domain.vendor.errors import VendorInUseError, VendorNotFoundError
from app.domain.vendor.values import VendorId
from tests.factories_deal import seed_deal
from tests.factories_vendor import make_vendor
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork


async def test_delete_used_vendor_is_rejected_with_count(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id)
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id, solution="ITDR")

    with pytest.raises(VendorInUseError) as raised:
        await DeleteVendor(uow_factory).execute(sap.id)

    assert str(raised.value) == "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)"
    assert (await uow.vendors.get(sap.id)).name == "SAP"


async def test_delete_unused_vendor_removes_it(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    await DeleteVendor(uow_factory).execute(sap.id)

    assert [v.name for v in await uow.vendors.list()] == ["Oracle"]
    assert uow.commits == 1


async def test_delete_vendor_ignores_usage_of_other_vendors(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)
    await seed_deal(uow, code="20261016-A001", vendor_id=oracle.id)

    await DeleteVendor(uow_factory).execute(sap.id)

    assert [v.name for v in await uow.vendors.list()] == ["Oracle"]


async def test_delete_missing_vendor_raises_not_found(uow_factory: UnitOfWorkFactory) -> None:
    with pytest.raises(VendorNotFoundError):
        await DeleteVendor(uow_factory).execute(VendorId(new_id()))


async def test_solution_use_cases_are_gone() -> None:
    import importlib  # noqa: PLC0415

    for module in ("register_solution", "rename_solution", "delete_solution"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(f"app.application.vendor.{module}")
