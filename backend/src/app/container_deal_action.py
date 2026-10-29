"""Deal Action 유스케이스를 만드는 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.deal_action.change_next_action_status import ChangeNextActionStatus
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.list_deal_actions import ListDealActions
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.update_deal_action import UpdateDealAction

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class DealActionUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock

    def register_deal_action(self) -> RegisterDealAction:
        return RegisterDealAction(self._uow, self._clock)

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
