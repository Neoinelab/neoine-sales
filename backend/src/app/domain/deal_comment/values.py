"""Comment 본문 규칙(CM-R1): NUL 거부 -> (필수만) 빈 값 거부 -> 앞뒤 공백 제거. 길이 상한 없음."""

from typing import NewType

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

DealCommentId = NewType("DealCommentId", int)

COMMENT_BLANK = "Comment를 입력하세요."


def optional_comment(raw: str) -> str | None:
    """선택인 곳(Action 등록·종료 Comment)의 본문. 비었거나 공백뿐이면 None(Comment 없음)."""
    reject_nul(raw, "Comment")
    return raw.strip() or None


def comment_body(raw: str) -> str:
    """필수인 곳(작성·수정)의 본문. 비었거나 공백뿐이면 InvalidValueError."""
    text = optional_comment(raw)
    if text is None:
        raise InvalidValueError(COMMENT_BLANK)
    return text
