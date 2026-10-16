from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import NewType, Self
from uuid import UUID

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

DealActionId = NewType("DealActionId", UUID)

PROGRESS_REQUIRED = "진행사항을 입력하세요."
NEXT_ACTION_REQUIRED = "Next Action을 입력하세요."
DUE_DATE_REQUIRED = "Due Date를 입력하세요."


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


# 화면에 보이는 순서대로다(통화, 미팅, ...).
ACTION_TYPE_LABELS = MappingProxyType(
    {
        ActionType.CALL: "통화",
        ActionType.MEETING: "미팅",
        ActionType.EMAIL: "이메일",
        ActionType.DEMO: "데모",
        ActionType.PROPOSAL: "제안",
        ActionType.NEGOTIATION: "협상",
        ActionType.CONTRACT: "계약",
        ActionType.OTHER: "기타",
    }
)


@dataclass(frozen=True, slots=True)
class ActionContent:
    """Action 한 건의 내용: 무엇을 했고(진행사항), 다음에 무엇을 언제까지 할 것인가.

    세 텍스트의 길이에는 상한이 없다. 검증은 `parse`가 한다(trim, NUL 거부, 필수).
    """

    action_type: ActionType
    action: str
    next_action: str
    due_date: date
    memo: str

    @classmethod
    def parse(
        cls,
        *,
        action_type: ActionType,
        action: str,
        next_action: str,
        due_date: date | None,
        memo: str,
    ) -> Self:
        """NUL -> 진행사항 -> Next Action -> Due Date 순으로 검사한다(화면 검증 순서와 같다)."""
        for text, name in ((action, "진행사항"), (next_action, "Next Action"), (memo, "Memo")):
            reject_nul(text, name)
        action, next_action, memo = action.strip(), next_action.strip(), memo.strip()
        if not action:
            raise InvalidValueError(PROGRESS_REQUIRED)
        if not next_action:
            raise InvalidValueError(NEXT_ACTION_REQUIRED)
        if due_date is None:
            raise InvalidValueError(DUE_DATE_REQUIRED)
        if isinstance(due_date, datetime):
            raise InvalidValueError("Due Date는 시각 없는 날짜여야 합니다.")
        return cls(action_type, action, next_action, due_date, memo)
