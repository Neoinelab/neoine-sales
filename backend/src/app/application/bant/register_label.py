from typing import TYPE_CHECKING

from app.application.bant.dto import LabelUsage
from app.domain.bant.entities import BantLabel
from app.domain.bant.rules import ensure_unique_label_name
from app.domain.bant.values import normalize_label_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.bant.values import BantCategory
    from app.domain.user.value_objects import UserId


class RegisterBantLabel:
    """Label을 만든다(생성자 기록). 같은 구분을 잠근 채 이름 중복을 판단한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, category: BantCategory, name: str, actor_id: UserId) -> LabelUsage:
        clean = normalize_label_name(name)
        async with self._uow_factory() as uow:
            ensure_unique_label_name(await uow.bant_labels.list(category, for_update=True), clean)
            label = BantLabel.create(
                category=category, name=clean, created_by=actor_id, now=self._clock.now()
            )
            await uow.bant_labels.add(label)
            await uow.commit()
        return LabelUsage(label, 0)
