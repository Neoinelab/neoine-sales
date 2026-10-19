from typing import TYPE_CHECKING

from app.application.action_type.dto import ActionTypeUsage

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListActionTypes:
    """모든 유형을 기본 유형 먼저, 이어서 이름순으로 사용 수와 함께 돌려준다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> list[ActionTypeUsage]:
        async with self._uow_factory() as uow:
            counts = await uow.deal_actions.count_by_action_type()
            return [ActionTypeUsage(x, counts.get(x.id, 0)) for x in await uow.action_types.list()]
