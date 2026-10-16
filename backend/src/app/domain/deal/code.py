"""Deal code 값 객체: `YYYYMMDD-XXXX` (업무 날짜 8자리 - 영문 대문자·숫자 4자리)."""

import re
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from datetime import date

DEAL_CODE_ALPHABET = string.ascii_uppercase + string.digits
SUFFIX_LENGTH = 4
_SUFFIX_PATTERN = re.compile(r"[A-Z0-9]{4}")
_CODE_PATTERN = re.compile(
    r"[0-9]{8}-[A-Z0-9]{4}"
)  # fullmatch로만 쓴다($는 끝 줄바꿈을 통과시킨다)


@dataclass(frozen=True, slots=True)
class DealCode:
    """Deal의 업무 키이자 식별자. 형식이 틀리면 InvalidValueError."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CODE_PATTERN.fullmatch(self.value):
            raise InvalidValueError("Deal code 형식이 올바르지 않습니다.")

    @classmethod
    def issue(cls, day: date, suffix: str) -> DealCode:
        """업무 날짜와 무작위 4자리로 code를 만든다."""
        if not _SUFFIX_PATTERN.fullmatch(suffix):
            raise InvalidValueError("Deal code 끝 4자리는 영문 대문자와 숫자여야 합니다.")
        return cls(f"{day:%Y%m%d}-{suffix}")

    @classmethod
    def parse_or_none(cls, raw: str) -> DealCode | None:
        """경로 파라미터용. 형식이 틀리면 None(호출자가 '없음'으로 다룬다)."""
        try:
            return cls(raw)
        except InvalidValueError:
            return None
