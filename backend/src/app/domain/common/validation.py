"""값 객체가 공유하는 입력 검증 도우미."""

from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from datetime import datetime


def required_text(value: str, field: str, *, max_length: int) -> str:
    text = value.strip()
    if not text:
        raise InvalidValueError(f"{field}은(는) 비어 있을 수 없습니다")
    if len(text) > max_length:
        raise InvalidValueError(f"{field}은(는) {max_length}자를 넘을 수 없습니다")
    return text


def optional_text(value: str | None, field: str, *, max_length: int) -> str | None:
    if value is None or not value.strip():
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
