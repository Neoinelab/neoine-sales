from typing import TYPE_CHECKING

from app.application.vendor.dto import VendorUsage

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.domain.vendor.entities import Vendor
    from app.domain.vendor.values import VendorId


def vendor_usage(vendor: Vendor, by_vendor: Mapping[VendorId, int]) -> VendorUsage:
    return VendorUsage(vendor=vendor, usage_count=by_vendor.get(vendor.id, 0))
