"""Vendor Aggregate(AC-3·4): 이름만 가진 단순 Aggregate. 생성·이름 변경·삭제 가능 여부."""

import pytest

from app.domain.vendor.entities import Vendor
from app.domain.vendor.errors import VendorInUseError
from app.domain.vendor.values import VendorId
from tests.factories import NOW, later
from tests.factories_vendor import make_vendor
from tests.support.ids import new_id


def test_create_vendor_sets_name_and_times() -> None:
    vendor = Vendor.create(entity_id=VendorId(new_id()), name="SAP", now=NOW)

    assert vendor.name == "SAP"
    assert (vendor.created_at, vendor.updated_at) == (NOW, NOW)


def test_vendor_has_no_solution_members() -> None:
    vendor = make_vendor("SAP")

    for name in ("solutions", "add_solution", "rename_solution", "remove_solution", "has_solution"):
        assert not hasattr(vendor, name), name


def test_rename_vendor_touches_updated_at() -> None:
    vendor = make_vendor("SAP")

    vendor.rename("SAP Korea", later(5))

    assert vendor.name == "SAP Korea"
    assert (vendor.created_at, vendor.updated_at) == (NOW, later(5))


def test_ensure_deletable_rejects_used_vendor() -> None:
    vendor = make_vendor("SAP")

    with pytest.raises(VendorInUseError) as raised:
        vendor.ensure_deletable(2)

    assert str(raised.value) == "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)"
    assert raised.value.usage == 2


def test_ensure_deletable_allows_unused_vendor() -> None:
    vendor = make_vendor("SAP")

    vendor.ensure_deletable(0)


def test_solution_error_types_are_gone() -> None:
    from app.domain.vendor import errors, values  # noqa: PLC0415

    for name in ("SolutionNotFoundError", "DuplicateSolutionNameError", "SolutionInUseError"):
        assert not hasattr(errors, name), name
    for name in ("SolutionId", "SOLUTION_NAME_MAX", "normalize_solution_name"):
        assert not hasattr(values, name), name
