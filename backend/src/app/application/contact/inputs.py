from dataclasses import dataclass

from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul
from app.domain.contact.values import (
    WHITESPACE_MESSAGE,
    ContactDetails,
    ContactKind,
    has_whitespace,
)


@dataclass(frozen=True, slots=True)
class ContactInput:
    """연락처 등록·수정 입력(원시 타입). 수정 입력은 kind=None(종류는 바꾸지 않는다)."""

    kind: ContactKind | None
    company: str
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None

    def to_details(self) -> ContactDetails:
        """공백 검사를 먼저 하고(이메일·전화 포함), ""는 없는 값으로 본 뒤 형식을 검증한다."""
        for value in (self.company, self.name, self.email, self.phone):
            if value is not None and has_whitespace(value):
                raise InvalidValueError(WHITESPACE_MESSAGE)
        return ContactDetails(
            company=self.company,
            name=self.name,
            title=self.title,
            email=Email(_checked(self.email, "이메일")) if self.email else None,
            phone=PhoneNumber(_checked(self.phone, "전화번호")) if self.phone else None,
        )

    def require_kind(self) -> ContactKind:
        if self.kind is None:
            raise InvalidValueError("연락처 종류를 선택하세요.")
        return self.kind


def _checked(value: str | None, label: str) -> str:
    text = value or ""
    reject_nul(text, label)
    return text
