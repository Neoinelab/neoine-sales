from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.common.entity import AuditedEntity
from app.domain.deal_comment.errors import DealCommentDeleteForbiddenError
from app.domain.deal_comment.policy import can_delete_comment
from app.domain.deal_comment.values import DealCommentId

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.principal import Role
    from app.domain.deal.code import DealCode
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.user.value_objects import UserId


@dataclass(eq=False, kw_only=True)
class DealComment(AuditedEntity[DealCommentId]):
    """Deal에 연결된 글 한 건. 선택적으로 그 Deal의 Action 하나에 연결된다(CM-R2).

    본문·소속 Deal·연결 Action·작성자는 작성 뒤 바뀌지 않는다(수정 기능 폐지). 바뀌는 것은
    읽음 시각 `read_at`뿐이며, None이면 읽지 않음이다(CM-R26).
    """

    deal_code: DealCode
    action_id: DealActionId | None
    author_user_id: UserId
    body: str  # 이미 `comment_body`를 거친 값
    read_at: datetime | None = None

    @classmethod
    def write(  # noqa: PLR0913 - 작성 시점에 정해지는 값이 모두 독립적인 필수 입력
        cls,
        *,
        entity_id: DealCommentId,
        deal_code: DealCode,
        action_id: DealActionId | None,
        author_user_id: UserId,
        body: str,
        now: datetime,
        deal_owner_id: UserId,
    ) -> Self:
        return cls(
            id=entity_id,
            deal_code=deal_code,
            action_id=action_id,
            author_user_id=author_user_id,
            body=body,
            read_at=now if author_user_id == deal_owner_id else None,
            created_at=now,
            updated_at=now,
        )

    def mark_read(self, now: datetime) -> bool:
        """읽음으로 바꾼다. 이미 읽음이면 아무것도 바꾸지 않고 False."""
        if self.read_at is not None:
            return False
        self.read_at = now
        return True

    def ensure_deletable_by(self, user_id: UserId, role: Role) -> None:
        if not can_delete_comment(user_id, role, self.author_user_id):
            raise DealCommentDeleteForbiddenError
