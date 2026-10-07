"""연락처 값 객체: 이메일, 전화번호."""

import re
from dataclasses import dataclass

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign

EMAIL_MAX_LENGTH = 254
PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15  # E.164 최대 자릿수
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]+$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > EMAIL_MAX_LENGTH or not _EMAIL_PATTERN.match(normalized):
            raise InvalidValueError(f"이메일 형식이 올바르지 않습니다: {self.value!r}")
        assign(self, value=normalized)


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    value: str

    def __post_init__(self) -> None:
        text = self.value.strip()
        digits = sum(ch.isdigit() for ch in text)
        valid_length = PHONE_MIN_DIGITS <= digits <= PHONE_MAX_DIGITS
        if not text or not _PHONE_PATTERN.match(text) or not valid_length:
            raise InvalidValueError(f"전화번호 형식이 올바르지 않습니다: {self.value!r}")
        assign(self, value=text)
