"""코드(Status·Forecast) 값 객체와 상수."""

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import NewType

from app.domain.common.errors import InvalidValueError

CodeId = NewType("CodeId", int)

CODE_NAME_MAX = 50
PROBABILITY_HINT_MAX = 20
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


class CodeKind(StrEnum):
    """코드의 종류. 선언 순서가 표시 순서다."""

    STATUS = "status"
    FORECAST = "forecast"


class ForecastOutcome(StrEnum):
    """Forecast가 시스템에 알려 주는 결과. 일반 코드와 Status는 항상 OPEN이다."""

    OPEN = "open"
    WON = "won"
    LOST = "lost"


# 시스템 규칙이 key로 연결하는 코드. 삭제할 수 없고 이름·순서만 바꿀 수 있다.
LOCKED_KEYS = MappingProxyType(
    {
        CodeKind.STATUS: frozenset({"prospecting", "contract_completed"}),
        CodeKind.FORECAST: frozenset({"pipeline", "won", "lost"}),
    }
)


@dataclass(frozen=True, slots=True)
class CodeKey:
    """코드의 내부 고유 key. 소문자로 시작하고 소문자·숫자·밑줄만 쓴다(최대 50자)."""

    value: str

    def __post_init__(self) -> None:
        if not _KEY_PATTERN.fullmatch(self.value):
            raise InvalidValueError(
                "코드 key는 소문자로 시작하고 소문자, 숫자, '_'만 쓸 수 있습니다(50자 이내)"
            )
