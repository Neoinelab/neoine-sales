from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType
from uuid import UUID

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.principal import Principal

SessionId = NewType("SessionId", UUID)


@dataclass(eq=False, kw_only=True)
class AuthSession:
    """서버가 보관하는 로그인 세션. 브라우저에는 토큰만 주고, 저장소에는 그 해시만 둔다."""

    id: SessionId
    principal: Principal
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        require_aware(self.expires_at, "expires_at")
        if self.revoked_at is not None:
            require_aware(self.revoked_at, "revoked_at")
        if self.expires_at <= self.created_at:
            raise InvalidValueError("세션 만료 시각은 생성 시각보다 뒤여야 합니다")

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at

    def revoke(self, now: datetime) -> None:
        if self.revoked_at is not None:
            raise InvalidStateError("이미 폐기된 세션입니다")
        self.revoked_at = require_aware(now, "now")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AuthSession) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
