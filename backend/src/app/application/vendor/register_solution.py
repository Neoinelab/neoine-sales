from typing import TYPE_CHECKING

from app.application.vendor.dto import SolutionUsage
from app.domain.vendor.values import normalize_solution_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.vendor.values import VendorId


class RegisterSolution:
    """Vendor 안에 Solution을 만든다. Vendor 행을 잠근 채 이름 중복을 판단한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, vendor_id: VendorId, name: str) -> SolutionUsage:
        clean = normalize_solution_name(name)
        async with self._uow_factory() as uow:
            vendor = await uow.vendors.get(vendor_id, for_update=True)
            solution = vendor.add_solution(clean, self._clock.now())
            await uow.vendors.update(vendor)
            await uow.commit()
        return SolutionUsage(vendor_id, solution, 0)
