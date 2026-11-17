from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from app.application.deal_comment.views import UnreadCommentCounts
    from app.domain.deal.code import DealCode
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.deal_comment.entities import DealComment
    from app.domain.deal_comment.values import DealCommentId


class DealCommentRepository(Protocol):
    """Deal 소속 Comment 저장소. 삭제는 물리 삭제이고 Action·Deal 삭제는 DB가 CASCADE로 지운다."""

    async def add(self, comment: DealComment) -> None:
        """같은 id는 AlreadyExistsError, 소속 Deal이 없으면 DealNotFoundError.

        연결 Action이 없거나 다른 Deal 소속이면 InvalidReferenceError("Action"),
        작성자 users 행이 없으면 InvalidReferenceError("사용자").
        """
        ...

    async def get(self, comment_id: DealCommentId, *, for_update: bool = False) -> DealComment:
        """없으면 DealCommentNotFoundError. for_update면 행을 잠근다."""
        ...

    async def list_for_deal(
        self, deal_code: DealCode, *, action_id: DealActionId | None = None
    ) -> Sequence[DealComment]:
        """그 Deal 소속 Comment 전부(action_id를 주면 그 Action의 것만).

        created_at 내림차순, 같으면 id 내림차순(최근순)이다.
        """
        ...

    async def mark_read(
        self, deal_code: DealCode, comment_ids: Sequence[DealCommentId], at: datetime
    ) -> None:
        """그 Deal 소속이고 read_at이 비어 있는 행만 at으로 채운다. 그 밖의 id는 건너뛴다."""
        ...

    async def unread_counts(self, deal_code: DealCode) -> UnreadCommentCounts:
        """read_at이 비어 있는 Comment 수. by_action에는 1 이상인 Action만 담는다."""
        ...

    async def delete(self, comment_id: DealCommentId) -> None:
        """물리 삭제한다. 없으면 DealCommentNotFoundError."""
        ...

    async def count_for_action(self, action_id: DealActionId) -> int:
        """그 Action에 연결된 Comment 수(Action 삭제 이력의 건수)."""
        ...
