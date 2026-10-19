from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.action_type.entities import ActionType


@dataclass(frozen=True, slots=True)
class ActionTypeUsage:
    """유형과 그 유형을 쓰는 Action 수."""

    action_type: ActionType
    usage_count: int
