"""식별자 동등성, 생성·수정 시각, 소프트 삭제를 공유하는 엔티티 기반 클래스."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidStateError
from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class AuditedEntity[IdT]:
    id: IdT
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        require_aware(self.updated_at, "updated_at")
        if self.deleted_at is not None:
            require_aware(self.deleted_at, "deleted_at")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, now: datetime) -> None:
        if self.is_deleted:
            raise InvalidStateError("이미 삭제된 항목입니다")
        require_aware(now, "now")
        self.deleted_at = now
        self.updated_at = now

    def restore(self, now: datetime) -> None:
        if not self.is_deleted:
            raise InvalidStateError("삭제되지 않은 항목은 복원할 수 없습니다")
        require_aware(now, "now")
        self.deleted_at = None
        self.updated_at = now

    def _ensure_active(self) -> None:
        if self.is_deleted:
            raise InvalidStateError("삭제된 항목은 수정할 수 없습니다. 먼저 복원하세요")

    def _touch(self, now: datetime) -> None:
        self.updated_at = require_aware(now, "now")

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and other.id == self.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))
