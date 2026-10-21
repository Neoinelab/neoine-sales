from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, NewType, Self

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

if TYPE_CHECKING:
    from app.domain.action_type.values import ActionTypeRef

DealActionId = NewType("DealActionId", int)

ACTION_OR_NEXT_REQUIRED = "진행사항 또는 Next Action을 입력하세요."
DUE_DATE_REQUIRED = "Due Date를 입력하세요."
DUE_WITHOUT_NEXT = "Next Action 없이 Due Date를 입력할 수 없습니다."


@dataclass(frozen=True, slots=True)
class ActionContent:
    """Action 한 건의 내용: 한 일(진행사항)과 다음 계획(Next Action, Due Date). 각각 선택이다.

    둘 중 하나는 있어야 하고, Due Date는 Next Action이 있을 때만 있다(없는 값은 None).
    세 텍스트의 길이에는 상한이 없다. 검증은 `parse`가 한다(trim, NUL 거부, 필수).
    """

    action_type: ActionTypeRef
    action: str | None
    next_action: str | None
    due_date: date | None
    memo: str

    def __post_init__(self) -> None:
        if self.action is None and self.next_action is None:
            raise InvalidValueError(ACTION_OR_NEXT_REQUIRED)
        if (self.next_action is None) != (self.due_date is None):
            raise InvalidValueError(DUE_WITHOUT_NEXT if self.due_date else DUE_DATE_REQUIRED)

    @property
    def has_next_action(self) -> bool:
        return self.next_action is not None

    @classmethod
    def parse(
        cls,
        *,
        action_type: ActionTypeRef,
        action: str,
        next_action: str,
        due_date: date | None,
        memo: str,
    ) -> Self:
        """NUL -> 둘 다 비어 있음 -> Due Date 필수 -> Due Date만 있음 순으로 검사한다."""
        for text, name in ((action, "진행사항"), (next_action, "Next Action"), (memo, "Memo")):
            reject_nul(text, name)
        action_text, next_text = action.strip() or None, next_action.strip() or None
        if action_text is None and next_text is None:
            raise InvalidValueError(ACTION_OR_NEXT_REQUIRED)
        if next_text is not None and due_date is None:
            raise InvalidValueError(DUE_DATE_REQUIRED)
        if next_text is None and due_date is not None:
            raise InvalidValueError(DUE_WITHOUT_NEXT)
        if isinstance(due_date, datetime):
            raise InvalidValueError("Due Date는 시각 없는 날짜여야 합니다.")
        return cls(action_type, action_text, next_text, due_date, memo.strip())
