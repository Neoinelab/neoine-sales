from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, required_text

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId

SUBJECT_MAX = 200
NAME_MAX = 200


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    ADMINISTER = "administer"


class Role(StrEnum):
    ADMIN = "admin"
    SALES = "sales"
    USER = "user"

    def allows(self, permission: Permission) -> bool:
        return permission in _GRANTS[self]


_GRANTS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.SALES: frozenset({Permission.READ, Permission.WRITE}),
    Role.USER: frozenset({Permission.READ}),
}


@dataclass(frozen=True, slots=True)
class Principal:
    """로그인한 사용자. users 행의 id(user_id), 로그인 아이디(subject), 표시 정보, 앱 안의 역할."""

    user_id: UserId
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

    def can(self, permission: Permission) -> bool:
        return self.role.allows(permission)
