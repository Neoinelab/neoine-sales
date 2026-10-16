from typing import TYPE_CHECKING

from app.application.bant.dto import LabelUsage
from app.domain.bant.rules import ensure_unique_label_name
from app.domain.bant.values import normalize_label_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.bant.values import BantLabelId


class RenameBantLabel:
    """Label 이름을 바꾼다(기본 Label 포함). 같은 구분 안에서 이름이 겹치면 안 된다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, label_id: BantLabelId, name: str) -> LabelUsage:
        clean = normalize_label_name(name)
        async with self._uow_factory() as uow:
            label = await uow.bant_labels.get(label_id)
            siblings = await uow.bant_labels.list(label.category, for_update=True)
            ensure_unique_label_name(siblings, clean, self_id=label.id)
            label.rename(clean, self._clock.now())
            await uow.bant_labels.update(label)
            counts = await uow.deals.count_by_bant_label()
            await uow.commit()
        return LabelUsage(label, counts.get(label.id, 0))
