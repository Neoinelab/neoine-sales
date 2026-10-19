from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.action_type.values import ActionTypeId


class DeleteActionType:
    """유형을 물리 삭제한다. 쓰는 Action이 있으면 ActionTypeInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, type_id: ActionTypeId) -> None:
        async with self._uow_factory() as uow:
            action_type = await uow.action_types.get(type_id)
            await uow.action_types.list(for_update=True)
            counts = await uow.deal_actions.count_by_action_type()
            action_type.ensure_deletable(counts.get(action_type.id, 0))
            await uow.action_types.delete(action_type.id)
            await uow.commit()
