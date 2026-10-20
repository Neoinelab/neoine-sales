"""Action 등록·수정·삭제가 Deal 이력에 남기는 문구. 긴 문구는 `HistoryDraft`가 1,000자로 자른다."""

from typing import TYPE_CHECKING

from app.domain.deal.history import HistoryCategory, HistoryDraft

if TYPE_CHECKING:
    from app.domain.deal_action.next_action_status import NextActionStatusChange
    from app.domain.deal_action.value_objects import ActionContent

ACTION_TARGET = "Action"
NEXT_ACTION_TARGET = "Next Action"
DELETED_TEXT = "삭제"


def _next_action_text(content: ActionContent) -> str:
    return f"{content.next_action} (Due {content.due_date.isoformat()})" if content.due_date else ""


def action_summary(content: ActionContent) -> str:
    """'<유형> · <진행사항> / Next Action: <다음> (Due ..) / Memo: <메모>'. 빈 부분은 뺀다."""
    text = content.action_type.name
    if content.action:
        text += f" · {content.action}"
    if content.next_action:
        text += f" / Next Action: {_next_action_text(content)}"
    return f"{text} / Memo: {content.memo}" if content.memo else text


def _draft(before: str, after: str) -> HistoryDraft:
    return HistoryDraft(HistoryCategory.ACTION, ACTION_TARGET, before, after)


def action_created_draft(content: ActionContent) -> HistoryDraft:
    return _draft("", f"등록: {action_summary(content)}")


def action_updated_draft(before: ActionContent, after: ActionContent) -> HistoryDraft:
    return _draft(action_summary(before), f"수정: {action_summary(after)}")


def action_deleted_draft(content: ActionContent) -> HistoryDraft:
    return _draft(action_summary(content), DELETED_TEXT)


def next_action_status_draft(
    content: ActionContent, change: NextActionStatusChange
) -> HistoryDraft:
    """'<Next Action> (Due ..) · <이전 라벨>' -> '<새 라벨>[ / Memo: <종료 메모>]'."""
    before = f"{_next_action_text(content)} · {change.before.label}"
    after = change.after.label + (f" / Memo: {change.note}" if change.note else "")
    return HistoryDraft(HistoryCategory.ACTION, NEXT_ACTION_TARGET, before, after)
