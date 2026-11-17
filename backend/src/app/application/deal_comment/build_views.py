"""Comment 목록에 연결 Action 요약을 붙인다."""

from typing import TYPE_CHECKING

from app.application.deal_comment.views import DealCommentView, LinkedActionSummary

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.deal_comment.entities import DealComment


async def to_views(uow: UnitOfWork, comments: Sequence[DealComment]) -> list[DealCommentView]:
    """입력 순서를 지키고 같은 Action은 한 번만 읽는다."""
    summaries: dict[int, LinkedActionSummary] = {}
    views: list[DealCommentView] = []
    for comment in comments:
        summary = None
        if comment.action_id is not None:
            summary = summaries.get(comment.action_id)
            if summary is None:
                action = await uow.deal_actions.get(comment.action_id)
                summary = LinkedActionSummary(
                    id=action.id,
                    acted_on=action.acted_on,
                    action=action.content.action,
                    next_action=action.content.next_action,
                )
                summaries[comment.action_id] = summary
        views.append(DealCommentView(comment=comment, action=summary))
    return views
