from typing import TYPE_CHECKING

from app.application.ids import new_action_type_id
from app.domain.action_type.entities import ActionType
from app.domain.action_type.errors import ActionTypeNotFoundError, UnknownActionTypeError
from app.domain.action_type.rules import find_action_type
from app.domain.action_type.values import ActionTypeId, normalize_action_type_name

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.choice import CatalogChoice
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.action_type.values import ActionTypeRef
    from app.domain.user.value_objects import UserId


async def choose_action_type(
    uow: UnitOfWork, choice: CatalogChoice, actor_id: UserId, now: datetime
) -> ActionTypeRef:
    """선택을 유형 참조로 바꾼다. 없는 이름이면 같은 UoW에서 새 유형을 만든다.

    커밋은 호출한 유스케이스가 한다(뒤의 검증이 실패하면 새 유형도 롤백된다).
    """
    if choice.id is not None:
        return await _by_id(uow, choice.id)
    name = normalize_action_type_name(choice.name or "")
    found = find_action_type(await uow.action_types.list(for_update=True), name)
    if found is not None:
        return found.ref
    created = ActionType.create(
        entity_id=await new_action_type_id(uow.ids), name=name, created_by=actor_id, now=now
    )
    await uow.action_types.add(created)
    return created.ref


async def _by_id(uow: UnitOfWork, type_id: int) -> ActionTypeRef:
    try:
        return (await uow.action_types.get(ActionTypeId(type_id))).ref
    except ActionTypeNotFoundError:
        raise UnknownActionTypeError from None
