"""Comment가 연결할 Action 확인(CM-R5)."""

from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError, NotFoundError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.deal.code import DealCode
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId

ACTION_NOT_IN_DEAL = "선택한 Action이 이 Deal에 없습니다."


async def linked_action(
    uow: UnitOfWork, deal_code: DealCode, action_id: DealActionId | None
) -> DealAction | None:
    """연결 Action. action_id가 None이면 None, 없거나 다른 Deal 소속이면 InvalidValueError."""
    if action_id is None:
        return None
    try:
        action = await uow.deal_actions.get(action_id)
    except NotFoundError:
        raise InvalidValueError(ACTION_NOT_IN_DEAL) from None
    if action.deal_code != deal_code:
        raise InvalidValueError(ACTION_NOT_IN_DEAL)
    return action
