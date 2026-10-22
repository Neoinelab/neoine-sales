from typing import TYPE_CHECKING

from app.application.ids import new_vendor_id
from app.application.vendor.dto import VendorUsage
from app.domain.vendor.entities import Vendor
from app.domain.vendor.rules import ensure_unique_vendor_name
from app.domain.vendor.values import normalize_vendor_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class RegisterVendor:
    """Vendor를 만든다. Vendor 목록을 잠근 채 이름 중복을 판단한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, name: str) -> VendorUsage:
        clean = normalize_vendor_name(name)
        async with self._uow_factory() as uow:
            ensure_unique_vendor_name(await uow.vendors.list(for_update=True), clean)
            vendor = Vendor.create(
                entity_id=await new_vendor_id(uow.ids), name=clean, now=self._clock.now()
            )
            await uow.vendors.add(vendor)
            await uow.commit()
        return VendorUsage(vendor, 0)
