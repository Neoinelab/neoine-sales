"""Vendor·Solution 값 객체. 이름은 앞뒤 공백을 지우고 길이를 제한한다."""

from typing import NewType

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

VendorId = NewType("VendorId", int)
SolutionId = NewType("SolutionId", int)

VENDOR_NAME_MAX = 100
SOLUTION_NAME_MAX = 200


def _normalize(raw: str, label: str, limit: int) -> str:
    reject_nul(raw, f"{label} 이름")
    name = raw.strip()
    if not name:
        raise InvalidValueError(f"{label} 이름을 입력하세요.")
    if len(name) > limit:
        raise InvalidValueError(f"{label} 이름은 {limit}자 이내로 입력하세요.")
    return name


def normalize_vendor_name(raw: str) -> str:
    return _normalize(raw, "Vendor", VENDOR_NAME_MAX)


def normalize_solution_name(raw: str) -> str:
    return _normalize(raw, "Solution", SOLUTION_NAME_MAX)
