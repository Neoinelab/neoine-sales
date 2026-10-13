from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.deal_action.value_objects import DealActionDetails

if TYPE_CHECKING:
    from datetime import date, datetime

    from app.domain.deal.value_objects import DealId
    from app.domain.deal_action.value_objects import ActionType


@dataclass(frozen=True, slots=True)
class DealActionInput:
    """활동 등록·수정 입력. 소속 Deal은 경로로 정해지므로 포함하지 않는다."""

    action_type: ActionType
    action: str
    acted_at: datetime
    actor: str
    next_action: str
    due_date: date
    memo: str = ""

    def to_details(self, deal_id: DealId) -> DealActionDetails:
        return DealActionDetails(
            deal_id=deal_id,
            action_type=self.action_type,
            action=self.action,
            acted_at=self.acted_at,
            actor=self.actor,
            next_action=self.next_action,
            due_date=self.due_date,
            memo=self.memo,
        )
