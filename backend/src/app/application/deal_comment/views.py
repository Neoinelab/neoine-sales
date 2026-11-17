"""Comment 읽기 모델: 연결 Action 요약을 붙인 Comment와 읽지 않은 수(CM-R9, CM-R29)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date

    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.deal_comment.entities import DealComment


@dataclass(frozen=True, slots=True)
class LinkedActionSummary:
    id: DealActionId
    acted_on: date
    action: str | None
    next_action: str | None


@dataclass(frozen=True, slots=True)
class DealCommentView:
    """Comment와 그 연결 Action 요약(Deal Comment면 None)."""

    comment: DealComment
    action: LinkedActionSummary | None


@dataclass(frozen=True, slots=True)
class UnreadCommentCounts:
    """total은 Deal 전체, by_action은 1 이상인 Action만."""

    total: int
    by_action: Mapping[DealActionId, int]
