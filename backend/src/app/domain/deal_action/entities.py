from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.common.entity import AuditedEntity
from app.domain.common.validation import require_aware
from app.domain.deal_action.errors import (
    DealActionDeleteForbiddenError,
    DealActionEditForbiddenError,
)
from app.domain.deal_action.policy import can_edit_action
from app.domain.deal_action.value_objects import DealActionId

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.principal import Role
    from app.domain.deal.code import DealCode
    from app.domain.deal.sync_state import SyncState
    from app.domain.deal_action.value_objects import ActionContent
    from app.domain.user.value_objects import UserId


@dataclass(eq=False, kw_only=True)
class DealAction(AuditedEntity[DealActionId]):
    """Deal에서 일어난 활동 한 건. 수행 일시·수행자·스냅숏은 기록 때 정해지고 바뀌지 않는다.

    스냅숏은 기록 시점의 Status·Forecast다. 고칠 수 있는 것은 내용(`content`)뿐이다.
    """

    deal_code: DealCode
    content: ActionContent
    acted_at: datetime
    actor_user_id: UserId
    snapshot: SyncState

    @classmethod
    def record(  # noqa: PLR0913 - 기록 시점에 정해지는 값이 모두 독립적인 필수 입력
        cls,
        *,
        deal_code: DealCode,
        content: ActionContent,
        actor_user_id: UserId,
        snapshot: SyncState,
        now: datetime,
        entity_id: DealActionId | None = None,
    ) -> Self:
        return cls(
            id=entity_id or DealActionId(uuid4()),
            deal_code=deal_code,
            content=content,
            acted_at=now,
            actor_user_id=actor_user_id,
            snapshot=snapshot,
            created_at=now,
            updated_at=now,
        )

    def __post_init__(self) -> None:
        super().__post_init__()
        require_aware(self.acted_at, "acted_at")

    def revise(self, content: ActionContent, now: datetime) -> bool:
        """내용을 바꾼다. 같은 내용이면 아무것도 바꾸지 않고 False."""
        if content == self.content:
            return False
        self.content = content
        self._touch(now)
        return True

    def ensure_editable_by(self, user_id: UserId, role: Role) -> None:
        if not can_edit_action(user_id, role, self.actor_user_id):
            raise DealActionEditForbiddenError

    def ensure_deletable_by(self, user_id: UserId, role: Role) -> None:
        if not can_edit_action(user_id, role, self.actor_user_id):
            raise DealActionDeleteForbiddenError
