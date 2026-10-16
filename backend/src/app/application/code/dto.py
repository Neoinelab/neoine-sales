from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.code.entities import Code


@dataclass(frozen=True, slots=True)
class CodeSet:
    """모든 로그인 사용자가 읽는 코드 전체(Status와 Forecast)."""

    statuses: Sequence[Code]
    forecasts: Sequence[Code]


@dataclass(frozen=True, slots=True)
class CodeUsage:
    """코드와 그 코드를 쓰는 Deal 수."""

    code: Code
    usage_count: int
