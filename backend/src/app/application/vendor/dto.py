from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.vendor.entities import Vendor


@dataclass(frozen=True, slots=True)
class VendorUsage:
    """Vendor와 그 Vendor를 쓰는 Deal 수."""

    vendor: Vendor
    usage_count: int
