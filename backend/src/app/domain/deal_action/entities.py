from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.common.entity import AuditedEntity
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.common.validation import reject_nul, require_aware
from app.domain.deal_action.errors import (
    DealActionDeleteForbiddenError,
    DealActionEditForbiddenError,
    DealActionStatusForbiddenError,
)
from app.domain.deal_action.next_action_status import (
    NextActionState,
    NextActionStatus,
    NextActionStatusChange,
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
    next_action_state: NextActionState | None  # Next Action이 있는 Action에만 있다

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
            next_action_state=NextActionState.open() if content.has_next_action else None,
            created_at=now,
            updated_at=now,
        )

    def __post_init__(self) -> None:
        super().__post_init__()
        require_aware(self.acted_at, "acted_at")
        if self.content.has_next_action != (self.next_action_state is not None):
            raise InvalidValueError("Next Action과 상태는 함께 있거나 함께 없어야 합니다.")

    def revise(self, content: ActionContent, now: datetime) -> bool:
        """내용을 바꾼다. 같은 내용이면 아무것도 바꾸지 않고 False.

        Next Action을 비우면 상태를 없애고, 새로 채우면 Open이며, 이미 있던 것의 수정은
        (종료 상태여도) 상태를 그대로 둔다.
        """
        if content == self.content:
            return False
        if not content.has_next_action:
            self.next_action_state = None
        elif self.next_action_state is None:
            self.next_action_state = NextActionState.open()
        self.content = content
        self._touch(now)
        return True

    def change_next_action_status(
        self, status: NextActionStatus, note: str, now: datetime
    ) -> NextActionStatusChange:
        """Next Action 상태를 바꾼다. 종료 메모는 Memo 뒤에 줄바꿈으로 덧붙인다.

        검사 순서: 메모 NUL -> Open으로 되돌리며 메모 -> Next Action 없음 -> 같은 상태.
        """
        reject_nul(note, "메모")
        note = note.strip()
        if status is NextActionStatus.OPEN and note:
            raise InvalidValueError("Open으로 되돌릴 때는 메모를 남길 수 없습니다.")
        current = self.next_action_state
        if current is None:
            raise InvalidStateError("Next Action이 없는 Action은 상태를 바꿀 수 없습니다.")
        if current.status is status:
            raise InvalidStateError(f"이미 {status.label} 상태입니다.")
        new_state = NextActionState.of(status, now)
        if note:
            memo = f"{self.content.memo}\n{note}" if self.content.memo else note
            self.content = replace(self.content, memo=memo)
        self.next_action_state = new_state
        self._touch(now)
        return NextActionStatusChange(before=current.status, after=status, note=note)

    def ensure_status_changeable_by(self, user_id: UserId, role: Role) -> None:
        if not can_edit_action(user_id, role, self.actor_user_id):
            raise DealActionStatusForbiddenError

    def ensure_editable_by(self, user_id: UserId, role: Role) -> None:
        if not can_edit_action(user_id, role, self.actor_user_id):
            raise DealActionEditForbiddenError

    def ensure_deletable_by(self, user_id: UserId, role: Role) -> None:
        if not can_edit_action(user_id, role, self.actor_user_id):
            raise DealActionDeleteForbiddenError
