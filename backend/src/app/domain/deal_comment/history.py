"""Comment 작성·삭제가 Deal 이력에 남기는 문구(CM-R13). 긴 문구는 `HistoryDraft`가 자른다."""

from typing import TYPE_CHECKING

from app.domain.deal.history import HistoryCategory, HistoryDraft

if TYPE_CHECKING:
    from app.domain.deal_action.entities import DealAction

COMMENT_TARGET = "Comment"
DELETED_TEXT = "삭제"


def comment_target(action: DealAction | None) -> str:
    """Deal Comment는 'Comment', Action Comment는 'Action Comment (<수행일> <유형>)'."""
    if action is None:
        return COMMENT_TARGET
    return f"Action Comment ({action.acted_on.isoformat()} {action.content.action_type.name})"


def _draft(action: DealAction | None, before: str, after: str) -> HistoryDraft:
    return HistoryDraft(HistoryCategory.COMMENT, comment_target(action), before, after)


def comment_created_draft(body: str, action: DealAction | None) -> HistoryDraft:
    return _draft(action, "", f"등록: {body}")


def comment_deleted_draft(body: str, action: DealAction | None) -> HistoryDraft:
    return _draft(action, body, DELETED_TEXT)
