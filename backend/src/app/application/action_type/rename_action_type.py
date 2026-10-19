from typing import TYPE_CHECKING

from app.application.action_type.dto import ActionTypeUsage
from app.domain.action_type.rules import ensure_unique_action_type_name
from app.domain.action_type.values import normalize_action_type_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.action_type.values import ActionTypeId


class RenameActionType:
    """유형 이름을 바꾼다(기본 유형 포함). 다른 유형과 이름이 겹치면 안 된다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, type_id: ActionTypeId, name: str) -> ActionTypeUsage:
        clean = normalize_action_type_name(name)
        async with self._uow_factory() as uow:
            action_type = await uow.action_types.get(type_id)
            others = await uow.action_types.list(for_update=True)
            ensure_unique_action_type_name(others, clean, self_id=action_type.id)
            action_type.rename(clean, self._clock.now())
            await uow.action_types.update(action_type)
            counts = await uow.deal_actions.count_by_action_type()
            await uow.commit()
        return ActionTypeUsage(action_type, counts.get(action_type.id, 0))
