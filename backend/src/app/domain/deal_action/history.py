"""Action 등록·수정·삭제가 Deal 이력에 남기는 문구. 긴 문구는 `HistoryDraft`가 1,000자로 자른다."""

from typing import TYPE_CHECKING

from app.domain.deal.history import HistoryCategory, HistoryDraft

if TYPE_CHECKING:
    from datetime import date

    from app.domain.deal_action.next_action_status import NextActionStatusChange
    from app.domain.deal_action.value_objects import ActionContent

ACTION_TARGET = "Action"
NEXT_ACTION_TARGET = "Next Action"
DELETED_TEXT = "삭제"


def _next_action_text(content: ActionContent) -> str:
    return f"{content.next_action} (Due {content.due_date.isoformat()})" if content.due_date else ""


def action_summary(content: ActionContent) -> str:
    """'<유형> · <진행사항> / Next Action: <다음> (Due ..)'. 빈 부분은 뺀다."""
    text = content.action_type.name
    if content.action:
        text += f" · {content.action}"
    if content.next_action:
        text += f" / Next Action: {_next_action_text(content)}"
    return text


def _draft(before: str, after: str) -> HistoryDraft:
    return HistoryDraft(HistoryCategory.ACTION, ACTION_TARGET, before, after)


def action_created_draft(content: ActionContent) -> HistoryDraft:
    return _draft("", f"등록: {action_summary(content)}")


def action_updated_draft(
    before: ActionContent,
    after: ActionContent,
    *,
    acted_on: tuple[date, date] | None = None,
) -> HistoryDraft:
    """수정 이력. acted_on=(이전, 새)이면 양쪽 요약 끝에 ' / 수행일: YYYY-MM-DD'를 붙인다."""
    before_text, after_text = action_summary(before), action_summary(after)
    if acted_on is not None:
        before_text += f" / 수행일: {acted_on[0].isoformat()}"
        after_text += f" / 수행일: {acted_on[1].isoformat()}"
    return _draft(before_text, f"수정: {after_text}")


def action_deleted_draft(content: ActionContent, *, comment_count: int) -> HistoryDraft:
    """삭제 이력. 함께 지운 Action Comment가 있으면 변경 후에 그 건수를 붙인다(CM-R16)."""
    after = DELETED_TEXT
    if comment_count:
        after += f" (Comment {comment_count}건 함께 삭제)"
    return _draft(action_summary(content), after)


def next_action_status_draft(
    content: ActionContent, change: NextActionStatusChange
) -> HistoryDraft:
    """'<Next Action> (Due ..) · <이전 라벨>' -> '<새 라벨>'. 종료 Comment는 별도 Comment 줄이다."""
    before = f"{_next_action_text(content)} · {change.before.label}"
    return HistoryDraft(HistoryCategory.ACTION, NEXT_ACTION_TARGET, before, change.after.label)
