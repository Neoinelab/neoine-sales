from typing import TYPE_CHECKING

from app.application.vendor.dto import SolutionUsage, VendorUsage

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.domain.vendor.entities import Solution, Vendor
    from app.domain.vendor.values import SolutionId, VendorId


def vendor_usage(
    vendor: Vendor, by_vendor: Mapping[VendorId, int], by_solution: Mapping[SolutionId, int]
) -> VendorUsage:
    return VendorUsage(
        vendor=vendor,
        usage_count=by_vendor.get(vendor.id, 0),
        solutions=tuple(solution_usage(vendor.id, s, by_solution) for s in vendor.solutions),
    )


def solution_usage(
    vendor_id: VendorId, solution: Solution, by_solution: Mapping[SolutionId, int]
) -> SolutionUsage:
    return SolutionUsage(vendor_id, solution, by_solution.get(solution.id, 0))
