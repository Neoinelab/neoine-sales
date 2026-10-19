"""Action 유형 값 객체. 이름은 앞뒤 공백을 지우고 50자까지 쓴다."""

from dataclasses import dataclass
from typing import NewType
from uuid import UUID

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

ActionTypeId = NewType("ActionTypeId", UUID)

ACTION_TYPE_NAME_MAX = 50
ACTION_TYPE_REQUIRED = "유형을 입력하세요."
ACTION_TYPE_TOO_LONG = f"유형은 {ACTION_TYPE_NAME_MAX}자 이내로 입력하세요."


def normalize_action_type_name(raw: str) -> str:
    reject_nul(raw, "유형")
    name = raw.strip()
    if not name:
        raise InvalidValueError(ACTION_TYPE_REQUIRED)
    if len(name) > ACTION_TYPE_NAME_MAX:
        raise InvalidValueError(ACTION_TYPE_TOO_LONG)
    return name


@dataclass(frozen=True, slots=True)
class ActionTypeRef:
    """Action이 가리키는 유형의 표시용 참조. 저장은 id만, name은 읽을 때의 현재 이름."""

    id: ActionTypeId
    name: str
