from typing import TYPE_CHECKING

from app.application.vendor.usage import vendor_usage
from app.domain.vendor.rules import ensure_unique_vendor_name
from app.domain.vendor.values import normalize_vendor_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.vendor.dto import VendorUsage
    from app.domain.vendor.values import VendorId


class RenameVendor:
    """Vendor 이름을 바꾼다. 다른 Vendor와 대소문자 무시로 겹치면 안 된다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, vendor_id: VendorId, name: str) -> VendorUsage:
        clean = normalize_vendor_name(name)
        async with self._uow_factory() as uow:
            others = await uow.vendors.list(for_update=True)
            vendor = await uow.vendors.get(vendor_id)
            ensure_unique_vendor_name(others, clean, self_id=vendor.id)
            vendor.rename(clean, self._clock.now())
            await uow.vendors.update(vendor)
            result = vendor_usage(vendor, await uow.deals.count_by_vendor())
            await uow.commit()
        return result
