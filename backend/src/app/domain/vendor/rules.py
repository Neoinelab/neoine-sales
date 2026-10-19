from typing import TYPE_CHECKING

from app.domain.vendor.errors import DuplicateVendorNameError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.vendor.entities import Vendor
    from app.domain.vendor.values import VendorId


def ensure_unique_vendor_name(
    others: Sequence[Vendor], name: str, self_id: VendorId | None = None
) -> None:
    """다른 Vendor 중 대소문자 무시로 같은 이름이 있으면 DuplicateVendorNameError."""
    lowered = name.lower()
    if any(x.id != self_id and x.name.lower() == lowered for x in others):
        raise DuplicateVendorNameError(name)
