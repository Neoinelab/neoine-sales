from typing import TYPE_CHECKING

from app.application.deal_comment.build_views import to_views

if TYPE_CHECKING:
    from app.application.deal_comment.views import DealCommentView
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_comment.values import DealCommentId


class GetDealComment:
    """Comment 한 건과 연결 Action 요약. 없으면 DealCommentNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, comment_id: DealCommentId) -> DealCommentView:
        async with self._uow_factory() as uow:
            comment = await uow.deal_comments.get(comment_id)
            (view,) = await to_views(uow, [comment])
            return view
