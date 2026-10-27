"""LIKE/ILIKE 부분 일치 검색 공용 도우미. 여러 Repository의 키워드 검색이 함께 쓴다."""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, or_

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute

LIKE_ESCAPE = "\\"


def _escape(keyword: str) -> str:
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def like_pattern(keyword: str) -> str:
    """LIKE 와일드카드(% _)와 이스케이프 문자를 글자 그대로 찾도록 이스케이프한다."""
    return f"%{_escape(keyword)}%"


def like_prefix_pattern(keyword: str) -> str:
    """keyword로 시작하는 값을 찾는 패턴(뒤에만 %). 와일드카드는 글자 그대로 취급한다."""
    return f"{_escape(keyword)}%"


def keyword_filter(
    keyword: str, *columns: InstrumentedAttribute[str] | InstrumentedAttribute[str | None]
) -> ColumnElement[bool]:
    """키워드가 열 중 하나라도 대소문자 무시로 부분 일치하는 조건. NULL 열은 불일치."""
    pattern = like_pattern(keyword)
    return or_(*(column.ilike(pattern, escape=LIKE_ESCAPE) for column in columns))
