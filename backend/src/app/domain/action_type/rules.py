from typing import TYPE_CHECKING

from app.domain.action_type.errors import DuplicateActionTypeNameError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.action_type.entities import ActionType
    from app.domain.action_type.values import ActionTypeId


def find_action_type(types: Sequence[ActionType], name: str) -> ActionType | None:
    """이름이 대소문자 무시로 완전히 같은 유형. 없으면 None."""
    lowered = name.lower()
    return next((x for x in types if x.name.lower() == lowered), None)


def ensure_unique_action_type_name(
    types: Sequence[ActionType], name: str, self_id: ActionTypeId | None = None
) -> None:
    """다른 유형 중 대소문자 무시로 같은 이름이 있으면 DuplicateActionTypeNameError."""
    lowered = name.lower()
    if any(x.id != self_id and x.name.lower() == lowered for x in types):
        raise DuplicateActionTypeNameError(name)
