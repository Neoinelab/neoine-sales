"""파트너 회사 해석."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def resolve_company(raw: str, companies: Sequence[str]) -> str | None:
    """대소문자 무시로 같은 첫 표기(대표 표기). 공백 정리나 부분 일치는 하지 않는다."""
    wanted = raw.lower()
    return next((c for c in companies if c.lower() == wanted), None)
