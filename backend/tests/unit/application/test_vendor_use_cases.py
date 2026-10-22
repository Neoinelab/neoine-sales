"""Vendor 유스케이스: 조회(AC-1), 생성·이름 변경·이름 규칙(AC-3). Solution 관리는 폐지됐다.

삭제는 `test_vendor_delete.py`. 쓰기 유스케이스는 Vendor 행을 잠그고(`for_update`) 규칙을 판단한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.vendor.list_vendors import ListVendors
from app.application.vendor.register_vendor import RegisterVendor
from app.application.vendor.rename_vendor import RenameVendor
from app.domain.common.errors import InvalidValueError
from app.domain.vendor.errors import (
    DuplicateVendorNameError,
    VendorNotFoundError,
)
from app.domain.vendor.values import VendorId
from tests.factories_deal import seed_deal
from tests.factories_vendor import make_vendor
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _names(uow: FakeUnitOfWork) -> list[str]:
    return [v.name for v in await uow.vendors.list()]


# --- ListVendors (AC-1) ---


async def test_list_vendors_returns_usage_without_solutions(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap = make_vendor("sap")
    oracle = make_vendor("Oracle")
    zeta = make_vendor("Zeta")
    for vendor in (zeta, sap, oracle):
        await uow.vendors.add(vendor)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id, solution="ITDR")
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id)

    result = await ListVendors(uow_factory).execute()

    assert [u.vendor.name for u in result] == ["Oracle", "sap", "Zeta"]
    assert [u.usage_count for u in result] == [0, 2, 0]
    assert all(not hasattr(u, "solutions") for u in result)


async def test_list_vendors_of_an_empty_system_is_empty(uow_factory: UnitOfWorkFactory) -> None:
    assert await ListVendors(uow_factory).execute() == []


# --- RegisterVendor (AC-1·4·5) ---


async def test_register_vendor_returns_it_with_zero_usage(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    result = await RegisterVendor(uow_factory, clock).execute("  SAP ")

    stored = await uow.vendors.get(result.vendor.id)
    assert stored.name == "SAP"
    assert stored.created_at == stored.updated_at == clock.now()
    assert result.usage_count == 0
    assert not hasattr(result, "solutions")
    assert uow.commits == 1


async def test_register_vendor_with_existing_name_ignoring_case_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    await uow.vendors.add(make_vendor("SAP"))

    with pytest.raises(DuplicateVendorNameError):
        await RegisterVendor(uow_factory, clock).execute(" sap ")

    assert await _names(uow) == ["SAP"]


@pytest.mark.parametrize("name", ["", "   ", "a" * 101, "a\x00b"])
async def test_register_vendor_with_an_invalid_name_stores_nothing(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    with pytest.raises(InvalidValueError):
        await RegisterVendor(uow_factory, clock).execute(name)

    assert await _names(uow) == []
    assert uow.commits == 0


# --- RenameVendor (AC-2·5) ---


async def test_rename_vendor_returns_usage_count(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id)
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id)
    clock.advance(30)

    result = await RenameVendor(uow_factory, clock).execute(sap.id, "SAP Korea")

    assert (result.vendor.name, result.usage_count) == ("SAP Korea", 2)
    assert (await uow.vendors.get(sap.id)).updated_at == clock.now()


async def test_rename_vendor_to_its_own_name_in_other_case_is_allowed(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("Sap")
    await uow.vendors.add(sap)

    result = await RenameVendor(uow_factory, clock).execute(sap.id, "SAP")

    assert result.vendor.name == "SAP"


async def test_rename_vendor_to_another_vendors_name_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    with pytest.raises(DuplicateVendorNameError):
        await RenameVendor(uow_factory, clock).execute(sap.id, "ORACLE")

    assert (await uow.vendors.get(sap.id)).name == "SAP"


async def test_rename_missing_vendor_is_not_found(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(VendorNotFoundError):
        await RenameVendor(uow_factory, clock).execute(VendorId(new_id()), "X")


async def test_rename_vendor_with_a_blank_name_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)

    with pytest.raises(InvalidValueError):
        await RenameVendor(uow_factory, clock).execute(sap.id, "  ")
