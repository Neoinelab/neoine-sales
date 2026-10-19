"""Vendor·Solution 유스케이스: 조회(AC-1), 생성(AC-1·3·5), 이름 변경(AC-2·3·5), 이름 규칙(AC-4).

삭제는 `test_vendor_delete.py`. 쓰기 유스케이스는 Vendor 행을 잠그고(`for_update`) 규칙을 판단한다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.vendor.list_vendors import ListVendors
from app.application.vendor.register_solution import RegisterSolution
from app.application.vendor.register_vendor import RegisterVendor
from app.application.vendor.rename_solution import RenameSolution
from app.application.vendor.rename_vendor import RenameVendor
from app.domain.common.errors import InvalidValueError
from app.domain.vendor.errors import (
    DuplicateSolutionNameError,
    DuplicateVendorNameError,
    SolutionNotFoundError,
    VendorNotFoundError,
)
from app.domain.vendor.values import SolutionId, VendorId
from tests.factories import later
from tests.factories_deal import seed_deal
from tests.factories_vendor import make_vendor

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _names(uow: FakeUnitOfWork) -> list[str]:
    return [v.name for v in await uow.vendors.list()]


# --- ListVendors (AC-1) ---


async def test_list_vendors_orders_by_lower_name_then_id_with_solution_usage(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap = make_vendor("sap", ["zeta", "Alpha"])
    oracle = make_vendor("Oracle", ["EBS"])
    zeta = make_vendor("Zeta")
    for vendor in (zeta, sap, oracle):
        await uow.vendors.add(vendor)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id, solution_id=sap.solutions[1].id)
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id)

    result = await ListVendors(uow_factory).execute()

    assert [u.vendor.name for u in result] == ["Oracle", "sap", "Zeta"]
    listed_sap = result[1]
    assert listed_sap.usage_count == 2
    assert [(s.solution.name, s.usage_count) for s in listed_sap.solutions] == [
        ("Alpha", 1),
        ("zeta", 0),
    ]
    assert all(s.vendor_id == sap.id for s in listed_sap.solutions)
    assert [u.usage_count for u in result] == [0, 2, 0]


async def test_list_vendors_of_an_empty_system_is_empty(uow_factory: UnitOfWorkFactory) -> None:
    assert await ListVendors(uow_factory).execute() == []


# --- RegisterVendor (AC-1·4·5) ---


async def test_register_vendor_returns_it_with_zero_usage(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    result = await RegisterVendor(uow_factory, clock).execute("  SAP ")

    stored = await uow.vendors.get(result.vendor.id)
    assert (stored.name, stored.solutions) == ("SAP", [])
    assert stored.created_at == stored.updated_at == clock.now()
    assert (result.usage_count, result.solutions) == (0, ())
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
        await RenameVendor(uow_factory, clock).execute(VendorId(uuid4()), "X")


async def test_rename_vendor_with_a_blank_name_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)

    with pytest.raises(InvalidValueError):
        await RenameVendor(uow_factory, clock).execute(sap.id, "  ")


# --- RegisterSolution (AC-3·4·5) ---


async def test_register_solution_returns_it_with_zero_usage_and_keeps_vendor_updated_at(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)
    clock.advance(30)

    result = await RegisterSolution(uow_factory, clock).execute(sap.id, " S/4HANA ")

    assert (result.vendor_id, result.solution.name, result.usage_count) == (
        sap.id,
        "S/4HANA",
        0,
    )
    stored = await uow.vendors.get(sap.id)
    assert [s.id for s in stored.solutions] == [result.solution.id]
    assert stored.updated_at == sap.updated_at


async def test_register_solution_under_missing_vendor_is_not_found(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(VendorNotFoundError):
        await RegisterSolution(uow_factory, clock).execute(VendorId(uuid4()), "Cloud")


async def test_register_solution_with_same_name_ignoring_case_in_the_vendor_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP", ["Cloud"])
    await uow.vendors.add(sap)

    with pytest.raises(DuplicateSolutionNameError):
        await RegisterSolution(uow_factory, clock).execute(sap.id, "cloud")

    assert [s.name for s in (await uow.vendors.get(sap.id)).solutions] == ["Cloud"]


async def test_same_solution_name_under_two_vendors_is_allowed(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap, oracle = make_vendor("SAP", ["Cloud"]), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    result = await RegisterSolution(uow_factory, clock).execute(oracle.id, "Cloud")

    assert result.solution.name == "Cloud"


@pytest.mark.parametrize("name", ["", "   ", "a" * 201, "a\x00b"])
async def test_register_solution_with_an_invalid_name_stores_nothing(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)

    with pytest.raises(InvalidValueError):
        await RegisterSolution(uow_factory, clock).execute(sap.id, name)

    assert (await uow.vendors.get(sap.id)).solutions == []


# --- RenameSolution (AC-3·5) ---


async def test_rename_solution_returns_its_usage_count(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP", ["S/4"])
    await uow.vendors.add(sap)
    solution_id = sap.solutions[0].id
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id, solution_id=solution_id)
    clock.advance(30)

    result = await RenameSolution(uow_factory, clock).execute(sap.id, solution_id, "S/4HANA")

    assert (result.solution.name, result.usage_count, result.vendor_id) == ("S/4HANA", 1, sap.id)
    stored = (await uow.vendors.get(sap.id)).solution(solution_id)
    assert (stored.name, stored.updated_at) == ("S/4HANA", clock.now())


async def test_rename_solution_of_another_vendor_is_not_found(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap, oracle = make_vendor("SAP", ["Cloud"]), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    with pytest.raises(SolutionNotFoundError):
        await RenameSolution(uow_factory, clock).execute(oracle.id, sap.solutions[0].id, "X")

    assert [s.name for s in (await uow.vendors.get(sap.id)).solutions] == ["Cloud"]


async def test_rename_solution_of_missing_vendor_is_not_found(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(VendorNotFoundError):
        await RenameSolution(uow_factory, clock).execute(
            VendorId(uuid4()), SolutionId(uuid4()), "X"
        )


async def test_rename_solution_to_a_sibling_name_is_rejected_but_own_case_change_is_allowed(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP", ["Cloud", "ERP"])
    await uow.vendors.add(sap)
    cloud, erp = (s.id for s in sap.solutions)
    rename = RenameSolution(uow_factory, clock)

    with pytest.raises(DuplicateSolutionNameError):
        await rename.execute(sap.id, erp, "CLOUD")
    result = await rename.execute(sap.id, cloud, "CLOUD")

    assert result.solution.name == "CLOUD"


async def test_rename_solution_with_the_clock_at_a_later_time_keeps_creation_time(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    sap = make_vendor("SAP", ["Cloud"])
    await uow.vendors.add(sap)
    clock.advance(60)

    await RenameSolution(uow_factory, clock).execute(sap.id, sap.solutions[0].id, "Cloud2")

    stored = (await uow.vendors.get(sap.id)).solutions[0]
    assert (stored.created_at, stored.updated_at) == (later(0), clock.now())
