from typing import TYPE_CHECKING

from app.application.action_type.dto import ActionTypeUsage
from app.application.ids import new_action_type_id
from app.domain.action_type.entities import ActionType
from app.domain.action_type.rules import ensure_unique_action_type_name
from app.domain.action_type.values import normalize_action_type_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserId


class RegisterActionType:
    """유형을 만든다(생성자 기록). 목록을 잠근 채 이름 중복을 판단한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, name: str, actor_id: UserId) -> ActionTypeUsage:
        clean = normalize_action_type_name(name)
        async with self._uow_factory() as uow:
            ensure_unique_action_type_name(await uow.action_types.list(for_update=True), clean)
            created = ActionType.create(
                entity_id=await new_action_type_id(uow.ids),
                name=clean,
                created_by=actor_id,
                now=self._clock.now(),
            )
            await uow.action_types.add(created)
            await uow.commit()
        return ActionTypeUsage(created, 0)
