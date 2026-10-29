"""파트너 회사 해석과 Deal 연결 판정."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.partner_meeting.errors import DEAL_NOT_FOUND, DEAL_NOT_LINKED

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.deal.code import DealCode


@dataclass(frozen=True, slots=True)
class LinkedDeals:
    """회사(대표 표기)의 활성 파트너 링크 Deal code 모음."""

    company: str
    codes: frozenset[DealCode]


def resolve_company(raw: str, companies: Sequence[str]) -> str | None:
    """대소문자 무시로 같은 첫 표기(대표 표기). 공백 정리나 부분 일치는 하지 않는다."""
    wanted = raw.lower()
    return next((c for c in companies if c.lower() == wanted), None)


def deal_link_problem(
    code: DealCode | None, *, deal_exists: bool, linked: LinkedDeals
) -> str | None:
    """Deal이 없거나 형식이 틀리면 DEAL_NOT_FOUND, 회사와 연결돼 있지 않으면 DEAL_NOT_LINKED."""
    if code is None or not deal_exists:
        return DEAL_NOT_FOUND
    if code not in linked.codes:
        return DEAL_NOT_LINKED
    return None
