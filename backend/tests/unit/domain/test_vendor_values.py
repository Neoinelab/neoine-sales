"""Vendor 이름 규칙(AC-3): 앞뒤 공백 제거, 빈 값·길이·NUL 거부."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.vendor.values import (
    VENDOR_NAME_MAX,
    normalize_vendor_name,
)


def test_vendor_name_limit_is_100() -> None:
    assert VENDOR_NAME_MAX == 100


def test_vendor_name_is_trimmed() -> None:
    assert normalize_vendor_name("  SAP ") == "SAP"


@pytest.mark.parametrize("raw", ["", "   ", "\t"])
def test_blank_vendor_name_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidValueError) as raised:
        normalize_vendor_name(raw)

    assert str(raised.value) == "Vendor 이름을 입력하세요."


def test_vendor_name_allows_100_and_rejects_101() -> None:
    assert normalize_vendor_name("a" * 100) == "a" * 100
    with pytest.raises(InvalidValueError) as raised:
        normalize_vendor_name("a" * 101)

    assert str(raised.value) == "Vendor 이름은 100자 이내로 입력하세요."


def test_length_is_counted_after_trimming() -> None:
    assert normalize_vendor_name(" " + "a" * 100 + " ") == "a" * 100


def test_length_counts_code_points() -> None:
    assert normalize_vendor_name("😀" * 100) == "😀" * 100
    with pytest.raises(InvalidValueError):
        normalize_vendor_name("😀" * 101)


def test_nul_in_vendor_name_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        normalize_vendor_name("a\x00b")
