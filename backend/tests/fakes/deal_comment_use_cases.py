"""FakeUseCases에 섞어 쓰는 Deal Comment 유스케이스 조립(mixin).

유스케이스 모듈은 사용 시점에 가져온다. FakeUseCases는 Comment와 무관한 테스트도 쓰므로, 모듈
수준 import는 구현이 없는 동안 그 테스트의 수집까지 막는다. 메서드 이름은 web의
`UseCaseProvider` 계약이다: write_deal_comment, list_deal_comments, get_deal_comment,
delete_deal_comment, mark_deal_comments_read, count_unread_deal_comments.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.deal_comment.count_unread_deal_comments import CountUnreadDealComments
    from app.application.deal_comment.mark_deal_comments_read import MarkDealCommentsRead

    from app.application.deal_comment.delete_deal_comment import DeleteDealComment
    from app.application.deal_comment.get_deal_comment import GetDealComment
    from app.application.deal_comment.list_deal_comments import ListDealComments
    from app.application.deal_comment.write_deal_comment import WriteDealComment
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class DealCommentUseCases:
    """`_comment_uow_factory()`와 `clock`을 가진 클래스에 섞는다."""

    clock: Clock

    def _comment_uow_factory(self) -> UnitOfWorkFactory:
        raise NotImplementedError

    def write_deal_comment(self) -> WriteDealComment:
        from app.application.deal_comment.write_deal_comment import (  # noqa: PLC0415
            WriteDealComment,
        )

        return WriteDealComment(self._comment_uow_factory(), self.clock)

    def list_deal_comments(self) -> ListDealComments:
        from app.application.deal_comment.list_deal_comments import (  # noqa: PLC0415
            ListDealComments,
        )

        return ListDealComments(self._comment_uow_factory())

    def get_deal_comment(self) -> GetDealComment:
        from app.application.deal_comment.get_deal_comment import GetDealComment  # noqa: PLC0415

        return GetDealComment(self._comment_uow_factory())

    def delete_deal_comment(self) -> DeleteDealComment:
        from app.application.deal_comment.delete_deal_comment import (  # noqa: PLC0415
            DeleteDealComment,
        )

        return DeleteDealComment(self._comment_uow_factory(), self.clock)

    def mark_deal_comments_read(self) -> MarkDealCommentsRead:
        from app.application.deal_comment.mark_deal_comments_read import (  # noqa: PLC0415
            MarkDealCommentsRead,
        )

        return MarkDealCommentsRead(self._comment_uow_factory(), self.clock)

    def count_unread_deal_comments(self) -> CountUnreadDealComments:
        from app.application.deal_comment.count_unread_deal_comments import (  # noqa: PLC0415
            CountUnreadDealComments,
        )

        return CountUnreadDealComments(self._comment_uow_factory())
