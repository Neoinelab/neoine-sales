"""DirectorySettings 필드 검증 규칙(DS-3~5). 위반 메시지에는 영문 필드 이름을 넣는다."""

import re
import unicodedata

from app.domain.common.errors import InvalidValueError

PLACEHOLDER = "{login_id}"
BIND_ACCOUNT_MAX = 256
DN_FILTER_MAX = 512


def _has_control(value: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" for ch in value)


def check_text(value: str, field: str, *, max_length: int) -> None:
    if not value:
        raise InvalidValueError(f"{field}은(는) 비어 있을 수 없습니다")
    if len(value) > max_length:
        raise InvalidValueError(f"{field}은(는) {max_length}자를 넘을 수 없습니다")
    if _has_control(value):
        raise InvalidValueError(f"{field}에는 제어문자를 쓸 수 없습니다")


def check_template(value: str, field: str, *, max_length: int) -> None:
    check_text(value, field, max_length=max_length)
    if value.count(PLACEHOLDER) != 1 or re.search(r"[{}]", value.replace(PLACEHOLDER, "")):
        raise InvalidValueError(
            f"{field}에는 {PLACEHOLDER}가 정확히 한 번 있어야 하고 다른 중괄호는 쓸 수 없습니다"
        )


def check_filter(value: str, field: str) -> None:
    check_template(value, field, max_length=DN_FILTER_MAX)
    depth = 0
    for index, char in enumerate(value):
        depth += (char == "(") - (char == ")")
        if depth < 0 or (depth == 0 and index < len(value) - 1):
            break
    else:
        if depth == 0 and value.startswith("("):
            return
    raise InvalidValueError(f"{field}은(는) 괄호로 감싸야 하고 괄호 짝이 맞아야 합니다")


def check_range(value: int, field: str, *, low: int, high: int) -> None:
    if not low <= value <= high:
        raise InvalidValueError(f"{field}은(는) {low}~{high} 사이여야 합니다")
