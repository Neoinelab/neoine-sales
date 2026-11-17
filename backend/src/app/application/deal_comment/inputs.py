"""Comment 유스케이스 입력(원시 타입). 본문 검증은 도메인 `comment_body`가 한다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.deal_action.value_objects import DealActionId


@dataclass(frozen=True, slots=True)
class DealCommentInput:
    """Comment 작성 입력. action_id가 None이면 Deal Comment, 값이 있으면 그 Action의 Comment."""

    body: str
    action_id: DealActionId | None = None
