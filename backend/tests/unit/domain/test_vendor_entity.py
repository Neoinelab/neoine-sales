"""Vendor Aggregate: 이름만 가진 단순 Aggregate. 생성·이름 변경·삭제 가능 여부."""

import pytest

from app.domain.vendor.entities import Vendor
from app.domain.vendor.errors import VendorInUseError
from app.domain.vendor.values import VendorId
from tests.factories import NOW, later
from tests.factories_vendor import make_vendor
from tests.support.ids import new_id


def test_create_vendor_sets_name_and_times() -> None:
    """Vendor를 만들면 이름과 생성·수정 시각이 정해진다."""
    # when: 이름 SAP으로 Vendor를 만든다
    vendor = Vendor.create(entity_id=VendorId(new_id()), name="SAP", now=NOW)

    # then: 이름이 SAP이고 생성·수정 시각이 현재다
    assert vendor.name == "SAP"
    assert (vendor.created_at, vendor.updated_at) == (NOW, NOW)


def test_vendor_has_no_solution_members() -> None:
    """Vendor에는 Solution 관련 멤버가 없다."""
    # given: SAP Vendor
    vendor = make_vendor("SAP")

    # when·then: 예전 Solution 멤버 이름이 모두 없다
    for name in ("solutions", "add_solution", "rename_solution", "remove_solution", "has_solution"):
        assert not hasattr(vendor, name), name


def test_rename_vendor_touches_updated_at() -> None:
    """이름을 바꾸면 수정 시각이 갱신된다."""
    # given: SAP Vendor
    vendor = make_vendor("SAP")

    # when: 5분 뒤 SAP Korea로 이름을 바꾼다
    vendor.rename("SAP Korea", later(5))

    # then: 이름이 바뀌고 수정 시각만 5분 뒤다
    assert vendor.name == "SAP Korea"
    assert (vendor.created_at, vendor.updated_at) == (NOW, later(5))


def test_ensure_deletable_rejects_used_vendor() -> None:
    """사용 중인 Vendor는 삭제할 수 없고 사용 건수를 알려 준다."""
    # given: SAP Vendor
    vendor = make_vendor("SAP")

    # when·then: Deal 2건이 쓰는 상태로 삭제 가능 여부를 확인하면 VendorInUseError다
    with pytest.raises(VendorInUseError) as raised:
        vendor.ensure_deletable(2)

    # then: 문구와 사용 건수 2를 담는다
    assert str(raised.value) == "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)"
    assert raised.value.usage == 2


def test_ensure_deletable_allows_unused_vendor() -> None:
    """쓰이지 않는 Vendor는 삭제할 수 있다."""
    # given: SAP Vendor
    vendor = make_vendor("SAP")

    # when·then: 사용 건수 0으로 확인해도 오류가 없다
    vendor.ensure_deletable(0)


def test_solution_error_types_are_gone() -> None:
    """Solution 관련 오류·값 타입은 더 이상 없다."""
    from app.domain.vendor import errors, values  # noqa: PLC0415

    # when·then: 예전 Solution 오류·값 타입 이름이 모듈에 모두 없다
    for name in ("SolutionNotFoundError", "DuplicateSolutionNameError", "SolutionInUseError"):
        assert not hasattr(errors, name), name
    for name in ("SolutionId", "SOLUTION_NAME_MAX", "normalize_solution_name"):
        assert not hasattr(values, name), name
