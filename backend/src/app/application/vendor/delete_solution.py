from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.vendor.values import SolutionId, VendorId


class DeleteSolution:
    """Solution을 물리 삭제한다. Deal이 쓰면 SolutionInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, vendor_id: VendorId, solution_id: SolutionId) -> None:
        async with self._uow_factory() as uow:
            vendor = await uow.vendors.get(vendor_id, for_update=True)
            usage = (await uow.deals.count_by_solution()).get(solution_id, 0)
            vendor.remove_solution(solution_id, usage)
            await uow.vendors.update(vendor)
            await uow.commit()
