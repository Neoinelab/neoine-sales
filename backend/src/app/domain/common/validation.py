"""값 객체가 공유하는 입력 검증 도우미."""

from datetime import date
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from datetime import datetime

DATE_CRITERIA_MIN = date(1900, 1, 1)
DATE_CRITERIA_MAX = date(2999, 12, 31)


def check_date_in_bounds(value: date | None, field: str) -> None:
    """기간 조건 날짜가 DATE_CRITERIA_MIN~MAX 안인지 확인한다(극단 날짜의 window 계산 오류 방지)."""
    if value is not None and not DATE_CRITERIA_MIN <= value <= DATE_CRITERIA_MAX:
        raise InvalidValueError(
            f"{field}은(는) {DATE_CRITERIA_MIN.isoformat()}부터"
            f" {DATE_CRITERIA_MAX.isoformat()} 사이여야 합니다"
        )


def reject_nul(value: str, field: str) -> None:
    """PostgreSQL 텍스트 열에 저장할 수 없는 NUL 문자를 거절한다(공백으로 감싸도 거절)."""
    if "\x00" in value:
        raise InvalidValueError(f"{field}에는 NUL 문자를 쓸 수 없습니다")


def required_text(value: str, field: str, *, max_length: int) -> str:
    reject_nul(value, field)
    text = value.strip()
    if not text:
        raise InvalidValueError(f"{field}은(는) 비어 있을 수 없습니다")
    if len(text) > max_length:
        raise InvalidValueError(f"{field}은(는) {max_length}자를 넘을 수 없습니다")
    return text


def optional_text(value: str | None, field: str, *, max_length: int) -> str | None:
    if value is None:
        return None
    if "\x00" in value:
        raise InvalidValueError(f"{field}에는 NUL 문자를 쓸 수 없습니다")
    if not value.strip():
        return None
    return required_text(value, field, max_length=max_length)


def require_aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidValueError(f"{field}은(는) 시간대(timezone) 정보가 있어야 합니다")
    return value


def assign(instance: object, **values: object) -> None:
    """frozen dataclass의 __post_init__에서 정규화된 값을 다시 넣을 때 쓴다."""
    for name, value in values.items():
        object.__setattr__(instance, name, value)
