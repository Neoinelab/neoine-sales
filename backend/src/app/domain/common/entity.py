"""식별자 동등성과 생성·수정 시각을 공유하는 엔티티 기반 클래스."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class AuditedEntity[IdT]:
    id: IdT
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        require_aware(self.updated_at, "updated_at")

    def _touch(self, now: datetime) -> None:
        self.updated_at = require_aware(now, "now")

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and other.id == self.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))
