from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.common.entity import AuditedEntity
from app.domain.common.errors import InvalidStateError
from app.domain.deal_action.value_objects import DealActionDetails, DealActionId

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class DealAction(AuditedEntity[DealActionId]):
    details: DealActionDetails

    @classmethod
    def create(
        cls, details: DealActionDetails, now: datetime, *, entity_id: DealActionId | None = None
    ) -> Self:
        details.require_complete()
        return cls(
            id=entity_id or DealActionId(uuid4()), details=details, created_at=now, updated_at=now
        )

    def update(self, details: DealActionDetails, now: datetime) -> None:
        self._ensure_active()
        details.require_complete()
        if details.deal_id != self.details.deal_id:
            raise InvalidStateError("활동은 다른 Deal로 옮길 수 없습니다")
        self._touch(now)
        self.details = details
