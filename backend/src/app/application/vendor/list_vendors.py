from typing import TYPE_CHECKING

from app.application.vendor.usage import vendor_usage

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.vendor.dto import VendorUsage


class ListVendors:
    """모든 Vendor를 이름순으로, 소속 Solution과 사용 수를 함께 돌려준다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> list[VendorUsage]:
        async with self._uow_factory() as uow:
            by_vendor = await uow.deals.count_by_vendor()
            by_solution = await uow.deals.count_by_solution()
            return [vendor_usage(v, by_vendor, by_solution) for v in await uow.vendors.list()]
