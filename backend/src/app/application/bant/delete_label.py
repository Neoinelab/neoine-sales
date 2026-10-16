from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.bant.values import BantLabelId


class DeleteBantLabel:
    """Label을 물리 삭제한다. 사용 중이면 LabelInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, label_id: BantLabelId) -> None:
        async with self._uow_factory() as uow:
            label = await uow.bant_labels.get(label_id)
            await uow.bant_labels.list(label.category, for_update=True)
            counts = await uow.deals.count_by_bant_label()
            label.ensure_deletable(counts.get(label.id, 0))
            await uow.bant_labels.delete(label.id)
            await uow.commit()
