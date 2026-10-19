"""Action 등록·수정·삭제가 Deal 이력에 남기는 문구. 긴 문구는 `HistoryDraft`가 1,000자로 자른다."""

from typing import TYPE_CHECKING

from app.domain.deal.history import HistoryCategory, HistoryDraft

if TYPE_CHECKING:
    from app.domain.deal_action.value_objects import ActionContent

ACTION_TARGET = "Action"
DELETED_TEXT = "삭제"


def action_summary(content: ActionContent) -> str:
    """'<유형> · <진행사항> / Next Action: <다음> (Due YYYY-MM-DD)' 뒤에 Memo가 있으면 덧붙인다."""
    label = content.action_type.name
    text = (
        f"{label} · {content.action} / Next Action: {content.next_action} "
        f"(Due {content.due_date.isoformat()})"
    )
    return f"{text} / Memo: {content.memo}" if content.memo else text


def _draft(before: str, after: str) -> HistoryDraft:
    return HistoryDraft(HistoryCategory.ACTION, ACTION_TARGET, before, after)


def action_created_draft(content: ActionContent) -> HistoryDraft:
    return _draft("", f"등록: {action_summary(content)}")


def action_updated_draft(before: ActionContent, after: ActionContent) -> HistoryDraft:
    return _draft(action_summary(before), f"수정: {action_summary(after)}")


def action_deleted_draft(content: ActionContent) -> HistoryDraft:
    return _draft(action_summary(content), DELETED_TEXT)
