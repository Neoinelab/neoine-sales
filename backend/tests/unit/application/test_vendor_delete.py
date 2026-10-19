"""Vendor·Solution 삭제 유스케이스(AC-6, D10): 사용 중이면 409 계열,
미사용 Vendor는 소속 Solution과 함께."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.vendor.delete_solution import DeleteSolution
from app.application.vendor.delete_vendor import DeleteVendor
from app.domain.vendor.errors import (
    SolutionInUseError,
    SolutionNotFoundError,
    VendorInUseError,
    VendorNotFoundError,
)
from app.domain.vendor.values import SolutionId, VendorId
from tests.factories_deal import seed_deal
from tests.factories_vendor import make_vendor

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork


async def test_delete_vendor_used_by_a_deal_is_rejected_with_count(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap = make_vendor("SAP", ["S/4HANA"])
    await uow.vendors.add(sap)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id)
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id)

    with pytest.raises(VendorInUseError) as raised:
        await DeleteVendor(uow_factory).execute(sap.id)

    assert str(raised.value) == "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)"
    assert (await uow.vendors.get(sap.id)).name == "SAP"


async def test_delete_vendor_whose_solution_is_used_is_rejected_and_keeps_both(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap = make_vendor("SAP", ["S/4HANA", "BW"])
    await uow.vendors.add(sap)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id, solution_id=sap.solutions[0].id)

    with pytest.raises(VendorInUseError) as raised:
        await DeleteVendor(uow_factory).execute(sap.id)

    assert str(raised.value) == "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 1건)"
    kept = await uow.vendors.get(sap.id)
    assert sorted(s.name for s in kept.solutions) == ["BW", "S/4HANA"]


async def test_delete_unused_vendor_removes_its_solutions(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap, oracle = make_vendor("SAP", ["S/4HANA", "BW"]), make_vendor("Oracle", ["EBS"])
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    await DeleteVendor(uow_factory).execute(sap.id)

    assert [v.name for v in await uow.vendors.list()] == ["Oracle"]
    assert [s.name for s in (await uow.vendors.get(oracle.id)).solutions] == ["EBS"]
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


async def test_delete_missing_vendor_is_not_found(uow_factory: UnitOfWorkFactory) -> None:
    with pytest.raises(VendorNotFoundError):
        await DeleteVendor(uow_factory).execute(VendorId(uuid4()))


async def test_delete_solution_used_by_a_deal_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap = make_vendor("SAP", ["S/4HANA"])
    await uow.vendors.add(sap)
    solution_id = sap.solutions[0].id
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id, solution_id=solution_id)

    with pytest.raises(SolutionInUseError) as raised:
        await DeleteSolution(uow_factory).execute(sap.id, solution_id)

    assert str(raised.value) == "사용 중인 Solution은 삭제할 수 없습니다. (Deal 1건)"
    assert (await uow.vendors.get(sap.id)).has_solution(solution_id)


async def test_delete_unused_solution_succeeds_and_keeps_the_others(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap = make_vendor("SAP", ["S/4HANA", "BW"])
    await uow.vendors.add(sap)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id, solution_id=sap.solutions[0].id)

    await DeleteSolution(uow_factory).execute(sap.id, sap.solutions[1].id)

    assert [s.name for s in (await uow.vendors.get(sap.id)).solutions] == ["S/4HANA"]


async def test_delete_solution_of_another_vendor_is_not_found(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    sap, oracle = make_vendor("SAP", ["S/4HANA"]), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    with pytest.raises(SolutionNotFoundError):
        await DeleteSolution(uow_factory).execute(oracle.id, sap.solutions[0].id)

    assert (await uow.vendors.get(sap.id)).has_solution(sap.solutions[0].id)


async def test_delete_solution_of_missing_vendor_is_not_found(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with pytest.raises(VendorNotFoundError):
        await DeleteSolution(uow_factory).execute(VendorId(uuid4()), SolutionId(uuid4()))
