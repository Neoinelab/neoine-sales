"""Deal Comment 요청·응답 스키마. 본문 규칙(공백·NUL)은 도메인이 판정하며 길이 상한은 없다."""

from datetime import date
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field

from app.application.deal_comment.inputs import DealCommentInput
from app.domain.deal_action.value_objects import DealActionId
from app.domain.user.value_objects import UserId
from app.web.schemas.common import RequestModel, ResponseModel
from app.web.schemas.ids import BodyId
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.deal_comment.views import DealCommentView, UnreadCommentCounts
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class DealCommentCreateRequest(RequestModel):
    """action_id가 없거나 null이면 Deal Comment, 값이 있으면 그 Deal의 Action Comment다."""

    body: str
    action_id: BodyId | None = None

    def to_input(self) -> DealCommentInput:
        action_id = None if self.action_id is None else DealActionId(self.action_id)
        return DealCommentInput(body=self.body, action_id=action_id)


class DealCommentReadRequest(RequestModel):
    """읽음 처리할 Comment id(1~500개). 그 Deal 소속이 아니거나 없는 id는 서버가 건너뛴다."""

    comment_ids: Annotated[list[BodyId], Field(min_length=1, max_length=500)]


class DealCommentActionSummary(BaseModel):
    """Action에 연결된 Comment의 Action 요약."""

    id: int
    acted_on: date
    action: str | None
    next_action: str | None


class DealCommentResponse(ResponseModel):
    deal_code: str
    action_id: int | None
    action: DealCommentActionSummary | None
    body: str
    author: UserRef
    read_at: ServerDateTime | None

    @classmethod
    def from_view(
        cls, view: DealCommentView, refs: Mapping[UserId, DomainUserRef]
    ) -> DealCommentResponse:
        comment = view.comment
        linked = view.action
        return cls(
            id=comment.id,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            deal_code=comment.deal_code.value,
            action_id=comment.action_id,
            action=None
            if linked is None
            else DealCommentActionSummary(
                id=linked.id,
                acted_on=linked.acted_on,
                action=linked.action,
                next_action=linked.next_action,
            ),
            body=comment.body,
            author=ref_of(refs, comment.author_user_id),
            read_at=comment.read_at,
        )


class DealCommentList(BaseModel):
    """Deal 소속 Comment. 페이지는 없고 최근 것이 먼저다."""

    items: list[DealCommentResponse]


class ActionUnreadCount(BaseModel):
    action_id: int
    unread: int


class DealCommentCounts(BaseModel):
    """읽지 않은 Comment 수. by_action은 1 이상인 Action만."""

    unread: int
    by_action: list[ActionUnreadCount]

    @classmethod
    def from_counts(cls, counts: UnreadCommentCounts) -> DealCommentCounts:
        return cls(
            unread=counts.total,
            by_action=[
                ActionUnreadCount(action_id=action_id, unread=unread)
                for action_id, unread in counts.by_action.items()
            ],
        )


async def comment_responses(
    provider: UseCaseProvider, views: Sequence[DealCommentView]
) -> list[DealCommentResponse]:
    """작성자 표시 이름을 한 번에 풀어 응답 목록을 만든다."""
    refs = await resolve_refs(provider, [v.comment.author_user_id for v in views])
    return [DealCommentResponse.from_view(v, refs) for v in views]


async def comment_response(provider: UseCaseProvider, view: DealCommentView) -> DealCommentResponse:
    (item,) = await comment_responses(provider, [view])
    return item
