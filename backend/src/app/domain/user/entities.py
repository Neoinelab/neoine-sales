from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.auth.principal import NAME_MAX, Principal, Role
from app.domain.common.contact import EMAIL_MAX_LENGTH
from app.domain.common.entity import AuditedEntity
from app.domain.common.errors import InvalidStateError
from app.domain.common.validation import require_aware
from app.domain.user.messages import ALREADY_RESIGNED
from app.domain.user.profile import (
    UNSET,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from app.domain.user.value_objects import UserDeleteReason, UserId, UserRef

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.credentials import LoginId
    from app.domain.user.profile import ProfileChanges


@dataclass(eq=False, kw_only=True)
class User(AuditedEntity[UserId]):
    """이 시스템을 쓸 수 있도록 등록된 AD 계정.

    비밀번호 평문은 저장하지 않는다(대체 로그인용 해시는 별도 저장소).

    퇴사 처리된 행(deleted_at)은 이력 보존용 불변 기록이다. 복구하지 않고, 같은 login_id로
    다시 등록하면 항상 새 행(새 id)이 생긴다.
    """

    login_id: LoginId
    role: Role
    created_by_user_id: UserId
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    last_login_at: datetime | None = None
    deleted_at: datetime | None = None
    delete_reason: UserDeleteReason | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.last_login_at is not None:
            require_aware(self.last_login_at, "last_login_at")
        if self.deleted_at is not None:
            require_aware(self.deleted_at, "deleted_at")

    @classmethod
    def register(  # noqa: PLR0913 - 위치 2개 + 키워드 전용 6개가 모두 의미 있는 입력
        cls,
        login_id: LoginId,
        role: Role,
        *,
        entity_id: UserId,
        created_by_user_id: UserId,
        now: datetime,
        display_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Self:
        """입력한 이름·이메일·전화는 형식 위반·길이 초과를 거절한다(자르지 않음). 빈 값은 None."""
        return cls(
            id=entity_id,
            login_id=login_id,
            role=role,
            created_by_user_id=created_by_user_id,
            display_name=normalize_name(display_name, required=False),
            email=normalize_email(email),
            phone=normalize_phone(phone),
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def register_self(  # noqa: PLR0913 - 위치 2개 + 키워드 전용 5개가 모두 의미 있는 입력
        cls,
        login_id: LoginId,
        role: Role,
        *,
        entity_id: UserId,
        now: datetime,
        display_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Self:
        """스스로 등록한 행(최초 admin, 개발 로그인): 등록자가 자기 자신이다."""
        return cls.register(
            login_id,
            role,
            entity_id=entity_id,
            created_by_user_id=entity_id,
            now=now,
            display_name=display_name,
            email=email,
            phone=phone,
        )

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    def resign(self, now: datetime, reason: UserDeleteReason = UserDeleteReason.RESIGNED) -> None:
        """퇴사 처리한다. 이미 퇴사한 행은 다시 처리할 수 없다."""
        require_aware(now, "now")
        if not self.is_active:
            raise InvalidStateError(ALREADY_RESIGNED)
        self._touch(now)
        self.deleted_at = now
        self.delete_reason = reason

    def change_role(self, role: Role, now: datetime) -> bool:
        """역할을 바꾼다. 같은 역할이면 아무것도 바꾸지 않고 False. 퇴사한 행은 바꿀 수 없다."""
        require_aware(now, "now")
        if not self.is_active:
            raise InvalidStateError(ALREADY_RESIGNED)
        if role is self.role:
            return False
        self._touch(now)
        self.role = role
        return True

    def record_login(self, now: datetime, *, display_name: str | None, email: str | None) -> None:
        """로그인 성공 시각을 남기고 디렉터리의 표시 이름·메일로 프로필을 덮어쓴다."""
        self._touch(now)
        self.last_login_at = now
        self.display_name = _directory_text(display_name, NAME_MAX, truncate=True)
        mail = _directory_text(email, EMAIL_MAX_LENGTH, truncate=False)
        self.email = mail if mail is not None and "@" in mail else None

    def change_profile(self, changes: ProfileChanges, now: datetime, *, require_name: bool) -> bool:
        """보낸 값만 바꾼다(UNSET은 그대로, None·빈 값은 비움). 바뀐 게 없으면 False.

        퇴사한 행은 거절한다. require_name이면 이름을 비울 수 없다. 모든 값을 검증한 뒤에 적용한다.
        """
        require_aware(now, "now")
        if not self.is_active:
            raise InvalidStateError(ALREADY_RESIGNED)
        new_name = self.display_name
        new_email = self.email
        new_phone = self.phone
        if changes.display_name is not UNSET:
            new_name = normalize_name(changes.display_name, required=require_name)
        if changes.email is not UNSET:
            new_email = normalize_email(changes.email)
        if changes.phone is not UNSET:
            new_phone = normalize_phone(changes.phone)
        if (new_name, new_email, new_phone) == (self.display_name, self.email, self.phone):
            return False
        self._touch(now)
        self.display_name, self.email, self.phone = new_name, new_email, new_phone
        return True

    def record_password_login(self, now: datetime) -> None:
        """저장된 비밀번호 해시로 로그인한 시각만 남긴다. 표시 이름·메일·전화는 그대로 둔다."""
        require_aware(now, "now")
        if not self.is_active:
            raise InvalidStateError(ALREADY_RESIGNED)
        self._touch(now)
        self.last_login_at = now

    def record_fallback_login(self, now: datetime) -> None:
        """AD 대체 로그인 성공 시각만 남긴다(디렉터리 값이 없으므로 프로필은 그대로)."""
        self.record_password_login(now)

    def to_ref(self) -> UserRef:
        return UserRef(
            id=self.id,
            name=self.display_name or self.login_id.value,
            resigned=not self.is_active,
            role=self.role,
        )

    def to_principal(self) -> Principal:
        return Principal(
            user_id=self.id,
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
