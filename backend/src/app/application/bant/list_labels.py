from typing import TYPE_CHECKING

from app.application.bant.dto import LabelUsage

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListBantLabels:
    """모든 BANT Label을 구분 선언 순, 기본 Label 먼저 이름순으로 사용 수와 함께 돌려준다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> list[LabelUsage]:
        async with self._uow_factory() as uow:
            counts = await uow.deals.count_by_bant_label()
            return [LabelUsage(x, counts.get(x.id, 0)) for x in await uow.bant_labels.list()]
