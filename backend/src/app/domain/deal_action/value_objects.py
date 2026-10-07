from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType
from uuid import UUID

from app.domain.common.validation import assign, optional_text, require_aware, required_text

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.deal.value_objects import DealId

DealActionId = NewType("DealActionId", UUID)

TITLE_MAX = 200
CONTENT_MAX = 4000
ACTOR_MAX = 100


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
    """Deal에서 일어난 활동 한 건: 무엇을(유형·제목·내용), 누가, 언제 했는가."""

    deal_id: DealId
    action_type: ActionType
    title: str
    acted_at: datetime
    actor: str
    content: str = ""

    def __post_init__(self) -> None:
        require_aware(self.acted_at, "활동 일시")
        assign(
            self,
            title=required_text(self.title, "활동 제목", max_length=TITLE_MAX),
            actor=required_text(self.actor, "활동자", max_length=ACTOR_MAX),
            content=optional_text(self.content, "활동 내용", max_length=CONTENT_MAX) or "",
        )
