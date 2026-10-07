from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.common.entity import AuditedEntity
from app.domain.partner.value_objects import PartnerDetails, PartnerId

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Partner(AuditedEntity[PartnerId]):
    details: PartnerDetails

    @classmethod
    def create(
        cls, details: PartnerDetails, now: datetime, *, entity_id: PartnerId | None = None
    ) -> Self:
        return cls(
            id=entity_id or PartnerId(uuid4()), details=details, created_at=now, updated_at=now
        )

    def update(self, details: PartnerDetails, now: datetime) -> None:
        self._ensure_active()
        self._touch(now)
        self.details = details
