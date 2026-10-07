from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.common.entity import AuditedEntity
from app.domain.deal.value_objects import DealDetails, DealId

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Deal(AuditedEntity[DealId]):
    details: DealDetails

    @classmethod
    def create(
        cls, details: DealDetails, now: datetime, *, entity_id: DealId | None = None
    ) -> Self:
        return cls(id=entity_id or DealId(uuid4()), details=details, created_at=now, updated_at=now)

    def update(self, details: DealDetails, now: datetime) -> None:
        self._ensure_active()
        self._touch(now)
        self.details = details
