"""Vendor 이름 중복 규칙: 대소문자 무시, 자기 자신은 제외."""

import pytest

from app.domain.vendor.errors import DuplicateVendorNameError
from app.domain.vendor.rules import ensure_unique_vendor_name
from tests.factories_vendor import make_vendor


def test_duplicate_vendor_name_ignoring_case_is_rejected() -> None:
    """대소문자만 다른 Vendor 이름은 중복으로 거부한다."""
    # given: SAP와 Oracle이 있다
    others = [make_vendor("SAP"), make_vendor("Oracle")]

    # when: 소문자 sap로 중복 검사를 한다
    with pytest.raises(DuplicateVendorNameError) as raised:
        ensure_unique_vendor_name(others, "sap")

    # then: 중복 안내 메시지다
    assert str(raised.value) == "이미 있는 Vendor 이름입니다."


def test_vendor_may_keep_its_own_name_in_other_case() -> None:
    """Vendor는 자기 이름을 대소문자만 바꿔 유지할 수 있다."""
    # given: SAP와 Oracle이 있다
    sap = make_vendor("SAP")

    # when·then: SAP 자신의 이름을 Sap으로 검사해도 오류가 없다
    ensure_unique_vendor_name([sap, make_vendor("Oracle")], "Sap", self_id=sap.id)


def test_other_vendors_name_is_still_rejected_for_a_renaming_vendor() -> None:
    """이름을 바꾸는 Vendor도 다른 Vendor의 이름과는 중복으로 거부한다."""
    # given: SAP와 Oracle이 있다
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")

    # when·then: SAP의 이름을 ORACLE로 바꾸려 하면 중복 오류가 난다
    with pytest.raises(DuplicateVendorNameError):
        ensure_unique_vendor_name([sap, oracle], "ORACLE", self_id=sap.id)


def test_a_new_name_passes() -> None:
    """새 이름은 통과한다."""
    # when·then: 없는 이름으로 검사하면 오류가 없다
    ensure_unique_vendor_name([make_vendor("SAP")], "Microsoft")
