from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.vendor.entities import Vendor
    from app.domain.vendor.values import VendorId


class VendorRepository(Protocol):
    """Vendor Aggregate(소속 Solution 포함) 저장소 계약.

    이름은 대소문자 무시로 고유하다(Vendor는 전역, Solution은 같은 Vendor 안).
    """

    async def list(self, *, for_update: bool = False) -> Sequence[Vendor]:
        """소문자 이름(코드 포인트) 순, 동률은 id 순. 각 Vendor의 solutions도 같은 규칙.

        for_update=True면 트랜잭션이 끝날 때까지 Vendor 행을 잠근다.
        """
        ...

    async def get(self, vendor_id: VendorId, *, for_update: bool = False) -> Vendor:
        """소속 Solution 포함. 없으면 VendorNotFoundError."""
        ...

    async def add(self, vendor: Vendor) -> None:
        """같은 이름(대소문자 무시)이면 DuplicateVendorNameError. 새 Vendor는 Solution이 없다."""
        ...

    async def update(self, vendor: Vendor) -> None:
        """Vendor 이름·수정 시각과 Solution 목록을 맞춘다(새 것 추가, 바뀐 것 갱신, 빠진 것 삭제).

        없으면 VendorNotFoundError, 이름이 겹치면 DuplicateVendorNameError 또는
        DuplicateSolutionNameError, Deal이 쓰는 Solution을 지우려 하면 SolutionInUseError.
        """
        ...

    async def delete(self, vendor_id: VendorId) -> None:
        """소속 Solution과 함께 물리 삭제한다.

        없으면 VendorNotFoundError, Deal이 쓰면 VendorInUseError.
        """
        ...
