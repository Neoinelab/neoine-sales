"""Vendor·Solution 이름 규칙(AC-4): 앞뒤 공백 제거, 빈 값·길이·NUL 거부."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.vendor.values import (
    SOLUTION_NAME_MAX,
    VENDOR_NAME_MAX,
    normalize_solution_name,
    normalize_vendor_name,
)


def test_limits_are_100_and_200() -> None:
    assert (VENDOR_NAME_MAX, SOLUTION_NAME_MAX) == (100, 200)


def test_vendor_name_is_trimmed() -> None:
    assert normalize_vendor_name("  SAP ") == "SAP"


def test_solution_name_is_trimmed() -> None:
    assert normalize_solution_name("  S/4HANA\t") == "S/4HANA"


@pytest.mark.parametrize("raw", ["", "   ", "\t"])
def test_blank_vendor_name_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidValueError) as raised:
        normalize_vendor_name(raw)

    assert str(raised.value) == "Vendor 이름을 입력하세요."


@pytest.mark.parametrize("raw", ["", "   ", "\t"])
def test_blank_solution_name_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidValueError) as raised:
        normalize_solution_name(raw)

    assert str(raised.value) == "Solution 이름을 입력하세요."


def test_vendor_name_allows_100_and_rejects_101() -> None:
    assert normalize_vendor_name("a" * 100) == "a" * 100
    with pytest.raises(InvalidValueError) as raised:
        normalize_vendor_name("a" * 101)

    assert str(raised.value) == "Vendor 이름은 100자 이내로 입력하세요."


def test_solution_name_allows_200_and_rejects_201() -> None:
    assert normalize_solution_name("a" * 200) == "a" * 200
    with pytest.raises(InvalidValueError) as raised:
        normalize_solution_name("a" * 201)

    assert str(raised.value) == "Solution 이름은 200자 이내로 입력하세요."


def test_length_is_counted_after_trimming() -> None:
    assert normalize_vendor_name(" " + "a" * 100 + " ") == "a" * 100


def test_length_counts_code_points() -> None:
    assert normalize_vendor_name("😀" * 100) == "😀" * 100
    with pytest.raises(InvalidValueError):
        normalize_vendor_name("😀" * 101)


@pytest.mark.parametrize("normalize", [normalize_vendor_name, normalize_solution_name])
def test_nul_in_names_is_rejected(normalize: object) -> None:
    with pytest.raises(InvalidValueError):
        normalize("a\x00b")  # type: ignore[operator]
