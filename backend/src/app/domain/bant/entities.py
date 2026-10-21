from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.bant.errors import LabelInUseError
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.entity import AuditedEntity

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.user.value_objects import UserId


@dataclass(eq=False, kw_only=True)
class BantLabel(AuditedEntity[BantLabelId]):
    """BANT 구분 안의 Label. 기본 Label(시드)은 생성자가 없고 default_order를 가진다."""

    category: BantCategory
    name: str
    is_default: bool = False
    default_order: int | None = None
    created_by_user_id: UserId | None = None

    @classmethod
    def create(
        cls,
        *,
        entity_id: BantLabelId,
        category: BantCategory,
        name: str,
        created_by: UserId,
        now: datetime,
    ) -> Self:
        """사용자가 만드는 Label. 이름은 이미 정규화된 값이다."""
        return cls(
            id=entity_id,
            category=category,
            name=name,
            created_by_user_id=created_by,
            created_at=now,
            updated_at=now,
        )

    def rename(self, name: str, now: datetime) -> None:
        self.name = name
        self._touch(now)

    def ensure_deletable(self, usage: int) -> None:
        if usage > 0:
            raise LabelInUseError(usage)
