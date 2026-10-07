"""목록 조회 페이지 인자 규칙. 모든 Repository 구현이 같은 검증을 쓰도록 Port와 함께 둔다."""

from app.domain.common.errors import InvalidValueError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def check_page(offset: int, limit: int) -> None:
    if offset < 0:
        raise InvalidValueError("offset은 0 이상이어야 합니다")
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidValueError(f"limit은 1 이상 {MAX_LIMIT} 이하여야 합니다")
