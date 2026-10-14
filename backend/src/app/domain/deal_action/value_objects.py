from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, NewType
from uuid import UUID

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, optional_text, require_aware, required_text

if TYPE_CHECKING:
    from app.domain.deal.value_objects import DealId
    from app.domain.user.value_objects import UserId

DealActionId = NewType("DealActionId", UUID)

ACTION_MAX = 200
NEXT_ACTION_MAX = 200
MEMO_MAX = 4000


class ActionType(StrEnum):
    """Deal 진행 활동의 종류. 집합을 닫아 두어 검색 조건과 통계가 흔들리지 않게 한다."""

    CALL = "call"
    MEETING = "meeting"
    EMAIL = "email"
    DEMO = "demo"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CONTRACT = "contract"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class DealActionDetails:
    """Deal에서 일어난 활동 한 건: 무엇을 했고(진행내역), 다음에 무엇을 언제 할 것인가.

    next_action·due_date는 기존 행을 읽을 때만 None일 수 있다. 쓰기는 require_complete()로 막는다.
    """

    deal_id: DealId
    action_type: ActionType
    action: str
    acted_at: datetime
    actor_user_id: UserId
    next_action: str | None = None
    due_date: date | None = None
    memo: str = ""

    def __post_init__(self) -> None:
        require_aware(self.acted_at, "활동 일시")
        if self.due_date is not None and isinstance(self.due_date, datetime):
            raise InvalidValueError("계획 일정은 시각 없는 날짜여야 합니다")
        assign(
            self,
            action=required_text(self.action, "진행내역", max_length=ACTION_MAX),
            next_action=(
                None
                if self.next_action is None
                else required_text(self.next_action, "다음 진행 계획", max_length=NEXT_ACTION_MAX)
            ),
            memo=optional_text(self.memo, "메모", max_length=MEMO_MAX) or "",
        )

    def require_complete(self) -> None:
        """쓰기(등록·수정) 전에 다음 진행 계획과 계획 일정이 모두 있는지 확인한다."""
        if self.next_action is None:
            raise InvalidValueError("다음 진행 계획은 비어 있을 수 없습니다")
        if self.due_date is None:
            raise InvalidValueError("계획 일정은 비어 있을 수 없습니다")
