from typing import TYPE_CHECKING

from app.application.vendor.usage import solution_usage
from app.domain.vendor.values import normalize_solution_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.vendor.dto import SolutionUsage
    from app.domain.vendor.values import SolutionId, VendorId


class RenameSolution:
    """Solution 이름을 바꾼다. 같은 Vendor의 다른 Solution과 겹치면 안 된다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, vendor_id: VendorId, solution_id: SolutionId, name: str
    ) -> SolutionUsage:
        clean = normalize_solution_name(name)
        async with self._uow_factory() as uow:
            vendor = await uow.vendors.get(vendor_id, for_update=True)
            solution = vendor.rename_solution(solution_id, clean, self._clock.now())
            await uow.vendors.update(vendor)
            result = solution_usage(vendor_id, solution, await uow.deals.count_by_solution())
            await uow.commit()
        return result
