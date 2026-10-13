from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.auth.principal import NAME_MAX, SUBJECT_MAX, Principal, Role
from app.domain.common.contact import EMAIL_MAX_LENGTH
from app.domain.common.entity import AuditedEntity
from app.domain.common.validation import require_aware, required_text
from app.domain.user.value_objects import UserId

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.credentials import LoginId


@dataclass(eq=False, kw_only=True)
class User(AuditedEntity[UserId]):
    """이 시스템을 쓸 수 있도록 등록된 AD 계정. 비밀번호는 저장하지 않는다."""

    login_id: LoginId
    role: Role
    created_by: str
    display_name: str | None = None
    email: str | None = None
    last_login_at: datetime | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.created_by = required_text(self.created_by, "등록자", max_length=SUBJECT_MAX)
        if self.last_login_at is not None:
            require_aware(self.last_login_at, "last_login_at")

    @classmethod
    def register(
        cls,
        login_id: LoginId,
        role: Role,
        *,
        created_by: str,
        now: datetime,
        entity_id: UserId | None = None,
    ) -> Self:
        return cls(
            id=entity_id or UserId(uuid4()),
            login_id=login_id,
            role=role,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

    def record_login(self, now: datetime, *, display_name: str | None, email: str | None) -> None:
        """로그인 성공 시각을 남기고 디렉터리의 표시 이름·메일로 프로필을 덮어쓴다."""
        self._touch(now)
        self.last_login_at = now
        self.display_name = _directory_text(display_name, NAME_MAX, truncate=True)
        mail = _directory_text(email, EMAIL_MAX_LENGTH, truncate=False)
        self.email = mail if mail is not None and "@" in mail else None

    def to_principal(self) -> Principal:
        return Principal(
            subject=self.login_id.value,
            email=self.email,
            name=self.display_name or self.login_id.value,
            role=self.role,
        )


def _directory_text(value: str | None, max_length: int, *, truncate: bool) -> str | None:
    """디렉터리(외부)가 준 값은 로그인을 막지 않도록 길면 자르거나(표시 이름) 버린다(메일)."""
    text = (value or "").replace("\x00", "").strip()
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() if truncate else None
