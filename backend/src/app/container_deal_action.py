"""Deal Action·Deal Comment 유스케이스를 만드는 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.deal_action.change_next_action_status import ChangeNextActionStatus
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.list_deal_actions import ListDealActions
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.application.deal_comment.count_unread_deal_comments import CountUnreadDealComments
from app.application.deal_comment.delete_deal_comment import DeleteDealComment
from app.application.deal_comment.get_deal_comment import GetDealComment
from app.application.deal_comment.list_deal_comments import ListDealComments
from app.application.deal_comment.mark_deal_comments_read import MarkDealCommentsRead
from app.application.deal_comment.write_deal_comment import WriteDealComment

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class DealActionUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock
    _file_storage: FileStorage

    def register_deal_action(self) -> RegisterDealAction:
        return RegisterDealAction(self._uow, self._clock, self._file_storage)

    def get_deal_action(self) -> GetDealAction:
        return GetDealAction(self._uow)

    def list_deal_actions(self) -> ListDealActions:
        return ListDealActions(self._uow)

    def update_deal_action(self) -> UpdateDealAction:
        return UpdateDealAction(self._uow, self._clock)

    def change_next_action_status(self) -> ChangeNextActionStatus:
        return ChangeNextActionStatus(self._uow, self._clock)

    def delete_deal_action(self) -> DeleteDealAction:
        return DeleteDealAction(self._uow, self._clock)

    def write_deal_comment(self) -> WriteDealComment:
        return WriteDealComment(self._uow, self._clock)

    def list_deal_comments(self) -> ListDealComments:
        return ListDealComments(self._uow)

    def get_deal_comment(self) -> GetDealComment:
        return GetDealComment(self._uow)

    def mark_deal_comments_read(self) -> MarkDealCommentsRead:
        return MarkDealCommentsRead(self._uow, self._clock)

    def count_unread_deal_comments(self) -> CountUnreadDealComments:
        return CountUnreadDealComments(self._uow)

    def delete_deal_comment(self) -> DeleteDealComment:
        return DeleteDealComment(self._uow, self._clock)
