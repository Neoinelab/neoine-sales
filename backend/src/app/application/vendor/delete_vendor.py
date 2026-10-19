from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.vendor.values import VendorId


class DeleteVendor:
    """Vendor를 소속 Solution과 함께 물리 삭제한다. Deal이 쓰면 VendorInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, vendor_id: VendorId) -> None:
        async with self._uow_factory() as uow:
            vendor = await uow.vendors.get(vendor_id, for_update=True)
            vendor.ensure_deletable((await uow.deals.count_by_vendor()).get(vendor.id, 0))
            await uow.vendors.delete(vendor.id)
            await uow.commit()
