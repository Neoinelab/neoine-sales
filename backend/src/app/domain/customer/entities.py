from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.common.entity import AuditedEntity
from app.domain.customer.value_objects import CustomerDetails, CustomerId

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Customer(AuditedEntity[CustomerId]):
    details: CustomerDetails

    @classmethod
    def create(
        cls, details: CustomerDetails, now: datetime, *, entity_id: CustomerId | None = None
    ) -> Self:
        return cls(
            id=entity_id or CustomerId(uuid4()), details=details, created_at=now, updated_at=now
        )

    def update(self, details: CustomerDetails, now: datetime) -> None:
        self._ensure_active()
        self._touch(now)
        self.details = details
