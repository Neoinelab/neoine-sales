from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.vendor.entities import Vendor
    from app.domain.vendor.values import VendorId


class VendorRepository(Protocol):
    """Vendor 저장소 계약. 이름은 대소문자 무시로 고유하다."""

    async def list(self, *, for_update: bool = False) -> Sequence[Vendor]:
        """소문자 이름(코드 포인트) 순, 동률은 id 순.

        for_update=True면 트랜잭션이 끝날 때까지 Vendor 행을 잠근다.
        """
        ...

    async def get(self, vendor_id: VendorId, *, for_update: bool = False) -> Vendor:
        """없으면 VendorNotFoundError."""
        ...

    async def add(self, vendor: Vendor) -> None:
        """같은 이름(대소문자 무시)이면 DuplicateVendorNameError."""
        ...

    async def update(self, vendor: Vendor) -> None:
        """이름·수정 시각을 맞춘다. 없으면 VendorNotFoundError, 겹치면 DuplicateVendorNameError."""
        ...

    async def delete(self, vendor_id: VendorId) -> None:
        """물리 삭제한다. 없으면 VendorNotFoundError, Deal이 쓰면 VendorInUseError."""
        ...
