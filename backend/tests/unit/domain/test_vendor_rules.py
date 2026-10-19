"""Vendor 이름 중복 규칙(AC-5): 대소문자 무시, 자기 자신은 제외."""

import pytest

from app.domain.vendor.errors import DuplicateVendorNameError
from app.domain.vendor.rules import ensure_unique_vendor_name
from tests.factories_vendor import make_vendor


def test_duplicate_vendor_name_ignoring_case_is_rejected() -> None:
    others = [make_vendor("SAP"), make_vendor("Oracle")]

    with pytest.raises(DuplicateVendorNameError) as raised:
        ensure_unique_vendor_name(others, "sap")

    assert str(raised.value) == "이미 있는 Vendor 이름입니다."


def test_vendor_may_keep_its_own_name_in_other_case() -> None:
    sap = make_vendor("SAP")

    ensure_unique_vendor_name([sap, make_vendor("Oracle")], "Sap", self_id=sap.id)


def test_other_vendors_name_is_still_rejected_for_a_renaming_vendor() -> None:
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")

    with pytest.raises(DuplicateVendorNameError):
        ensure_unique_vendor_name([sap, oracle], "ORACLE", self_id=sap.id)


def test_a_new_name_passes() -> None:
    ensure_unique_vendor_name([make_vendor("SAP")], "Microsoft")
