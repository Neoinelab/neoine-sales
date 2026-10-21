"""BANT Label 값 객체. Label은 점수 없이 구분과 이름만 가진다."""

from enum import StrEnum
from typing import NewType

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

BantLabelId = NewType("BantLabelId", int)

LABEL_NAME_MAX = 50


class BantCategory(StrEnum):
    """BANT 구분. 선언 순서가 표시 순서다."""

    BUDGET = "budget"
    AUTHORITY = "authority"
    NEED = "need"
    TIMELINE = "timeline"


def normalize_label_name(raw: str) -> str:
    reject_nul(raw, "Label 이름")
    name = raw.strip()
    if not name:
        raise InvalidValueError("Label 이름을 입력하세요.")
    if len(name) > LABEL_NAME_MAX:
        raise InvalidValueError(f"Label 이름은 {LABEL_NAME_MAX}자 이내로 입력하세요.")
    return name
