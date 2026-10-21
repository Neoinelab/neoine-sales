"""Vendor Aggregate(AC-2·3·5·6): Solution은 Vendor 메서드로만 추가·변경·삭제된다."""

import pytest

from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError
from app.domain.vendor.entities import Vendor
from app.domain.vendor.errors import (
    DuplicateSolutionNameError,
    SolutionInUseError,
    SolutionNotFoundError,
    VendorInUseError,
)
from app.domain.vendor.values import SolutionId, VendorId
from tests.factories import NOW, later
from tests.factories_vendor import make_vendor
from tests.support.ids import new_id


def test_create_makes_a_vendor_without_solutions() -> None:
    vendor = Vendor.create(entity_id=VendorId(new_id()), name="SAP", now=NOW)

    assert (vendor.name, vendor.solutions) == ("SAP", [])
    assert (vendor.created_at, vendor.updated_at) == (NOW, NOW)


def test_rename_changes_the_name_and_updated_at() -> None:
    vendor = make_vendor("SAP")

    vendor.rename("SAP Korea", later(5))

    assert vendor.name == "SAP Korea"
    assert (vendor.created_at, vendor.updated_at) == (NOW, later(5))


def test_add_solution_appends_a_named_solution() -> None:
    vendor = make_vendor("SAP")

    solution = vendor.add_solution("S/4HANA", later(1), entity_id=SolutionId(new_id()))

    assert [s.name for s in vendor.solutions] == ["S/4HANA"]
    assert vendor.solutions[0] is solution
    assert (solution.created_at, solution.updated_at) == (later(1), later(1))
    assert vendor.has_solution(solution.id)


def test_add_solution_with_same_name_ignoring_case_is_rejected() -> None:
    vendor = make_vendor("SAP", ["Cloud"])

    with pytest.raises(DuplicateSolutionNameError) as raised:
        vendor.add_solution("cloud", later(1), entity_id=SolutionId(new_id()))

    assert str(raised.value) == "이 Vendor에 이미 있는 Solution 이름입니다."
    assert isinstance(raised.value, AlreadyExistsError)
    assert [s.name for s in vendor.solutions] == ["Cloud"]


def test_rename_solution_to_its_own_name_in_other_case_is_allowed() -> None:
    vendor = make_vendor("SAP", ["Cloud"])
    solution_id = vendor.solutions[0].id

    renamed = vendor.rename_solution(solution_id, "CLOUD", later(2))

    assert renamed.name == "CLOUD"
    assert vendor.solution(solution_id).updated_at == later(2)


def test_rename_solution_to_a_sibling_name_is_rejected() -> None:
    vendor = make_vendor("SAP", ["Cloud", "ERP"])

    with pytest.raises(DuplicateSolutionNameError):
        vendor.rename_solution(vendor.solutions[1].id, "cloud", later(1))

    assert [s.name for s in vendor.solutions] == ["Cloud", "ERP"]


def test_unknown_solution_raises_not_found() -> None:
    vendor = make_vendor("SAP", ["Cloud"])
    missing = SolutionId(new_id())

    with pytest.raises(SolutionNotFoundError) as raised:
        vendor.solution(missing)

    assert isinstance(raised.value, NotFoundError)
    assert not vendor.has_solution(missing)


def test_rename_unknown_solution_raises_not_found() -> None:
    vendor = make_vendor("SAP")

    with pytest.raises(SolutionNotFoundError):
        vendor.rename_solution(SolutionId(new_id()), "x", later(1))


def test_remove_solution_in_use_is_rejected_with_count() -> None:
    vendor = make_vendor("SAP", ["Cloud"])

    with pytest.raises(SolutionInUseError) as raised:
        vendor.remove_solution(vendor.solutions[0].id, usage=2)

    assert str(raised.value) == "사용 중인 Solution은 삭제할 수 없습니다. (Deal 2건)"
    assert raised.value.usage == 2
    assert isinstance(raised.value, InvalidStateError)
    assert len(vendor.solutions) == 1


def test_remove_unused_solution_drops_only_that_one() -> None:
    vendor = make_vendor("SAP", ["Cloud", "ERP"])
    cloud = vendor.solutions[0].id

    vendor.remove_solution(cloud, usage=0)

    assert [s.name for s in vendor.solutions] == ["ERP"]


def test_remove_unknown_solution_raises_not_found() -> None:
    vendor = make_vendor("SAP")

    with pytest.raises(SolutionNotFoundError):
        vendor.remove_solution(SolutionId(new_id()), usage=0)


def test_vendor_in_use_is_not_deletable() -> None:
    vendor = make_vendor("SAP")

    with pytest.raises(VendorInUseError) as raised:
        vendor.ensure_deletable(1)

    assert str(raised.value) == "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 1건)"
    assert raised.value.usage == 1


def test_unused_vendor_with_solutions_is_deletable() -> None:
    vendor = make_vendor("SAP", ["Cloud", "ERP"])

    vendor.ensure_deletable(0)


def test_rename_touches_updated_at_but_solution_changes_do_not() -> None:
    vendor = make_vendor("SAP", ["Cloud"])

    vendor.add_solution("ERP", later(10), entity_id=SolutionId(new_id()))
    vendor.rename_solution(vendor.solutions[0].id, "Cloud2", later(11))
    vendor.remove_solution(vendor.solutions[1].id, usage=0)
    assert vendor.updated_at == NOW

    vendor.rename("SAP2", later(12))
    assert vendor.updated_at == later(12)
