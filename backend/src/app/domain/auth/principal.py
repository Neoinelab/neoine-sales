from dataclasses import dataclass
from enum import StrEnum

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, required_text

SUBJECT_MAX = 200
NAME_MAX = 200


class Role(StrEnum):
    ADMIN = "admin"
    SALES = "sales"


@dataclass(frozen=True, slots=True)
class Principal:
    """로그인한 사용자. IdP가 보증한 식별자(subject)와 표시 정보, 앱 안에서의 역할."""

    subject: str
    email: str | None
    name: str
    role: Role

    def __post_init__(self) -> None:
        subject = required_text(self.subject, "사용자 식별자", max_length=SUBJECT_MAX)
        name = self.name.strip()[:NAME_MAX] or subject
        email = (self.email or "").strip().lower() or None
        if email is not None and "@" not in email:
            raise InvalidValueError(f"이메일 형식이 올바르지 않습니다: {self.email!r}")
        assign(self, subject=subject, name=name, email=email)
