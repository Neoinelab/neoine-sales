from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.action_type.errors import ActionTypeInUseError
from app.domain.action_type.values import ActionTypeId, ActionTypeRef
from app.domain.common.entity import AuditedEntity

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.user.value_objects import UserId


@dataclass(eq=False, kw_only=True)
class ActionType(AuditedEntity[ActionTypeId]):
    """Action 유형. 기본 유형(시드)은 생성자가 없고 default_order를 가진다."""

    name: str
    is_default: bool = False
    default_order: int | None = None
    created_by_user_id: UserId | None = None

    @classmethod
    def create(cls, *, name: str, created_by: UserId, now: datetime) -> Self:
        """사용자가 만드는 유형. 이름은 이미 정규화된 값이다."""
        return cls(
            id=ActionTypeId(uuid4()),
            name=name,
            created_by_user_id=created_by,
            created_at=now,
            updated_at=now,
        )

    def rename(self, name: str, now: datetime) -> None:
        self.name = name
        self._touch(now)

    def ensure_deletable(self, usage: int) -> None:
        if usage > 0:
            raise ActionTypeInUseError(usage)

    @property
    def ref(self) -> ActionTypeRef:
        return ActionTypeRef(self.id, self.name)
