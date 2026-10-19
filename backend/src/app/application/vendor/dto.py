from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.vendor.entities import Solution, Vendor
    from app.domain.vendor.values import VendorId


@dataclass(frozen=True, slots=True)
class SolutionUsage:
    """Solution과 그 Solution을 쓰는 Deal 수."""

    vendor_id: VendorId
    solution: Solution
    usage_count: int


@dataclass(frozen=True, slots=True)
class VendorUsage:
    """Vendor, 그 Vendor를 쓰는 Deal 수, 소속 Solution별 사용 수(vendor.solutions 순서)."""

    vendor: Vendor
    usage_count: int
    solutions: tuple[SolutionUsage, ...]
