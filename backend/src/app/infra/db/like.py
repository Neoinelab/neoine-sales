"""LIKE/ILIKE 부분 일치 검색 공용 도우미. 두 Repository의 키워드 검색이 함께 쓴다."""

LIKE_ESCAPE = "\\"


def like_pattern(keyword: str) -> str:
    """LIKE 와일드카드(% _)와 이스케이프 문자를 글자 그대로 찾도록 이스케이프한다."""
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
