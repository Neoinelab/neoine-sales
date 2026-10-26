from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class DealYearsView:
    earliest_year: int | None  # Deal이 없으면 None


class GetDealYears:
    """연도 선택지의 기준: Expected Close가 가장 이른 Deal의 연도(읽기 전용)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> DealYearsView:
        async with self._uow_factory() as uow:
            return DealYearsView(earliest_year=await uow.deals.earliest_revenue_year())
