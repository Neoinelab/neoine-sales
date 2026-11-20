"""Deal 목록 담당자 이름 검색(DL-R39)의 도메인 규칙: 상수와 퇴사자 표기 해석."""

from app.domain.user.value_objects import RESIGNED_SUFFIX  # 정본은 UserRef.label과 같은 곳

__all__ = ["OWNER_NAME_MAX", "RESIGNED_SUFFIX", "resigned_owner_name"]

OWNER_NAME_MAX = 100


def resigned_owner_name(text: str) -> str | None:
    """반각 "(퇴사)"로 끝나면 그 앞 글자 전체, 아니면 None."""
    if text.endswith(RESIGNED_SUFFIX):
        return text[: -len(RESIGNED_SUFFIX)]
    return None
