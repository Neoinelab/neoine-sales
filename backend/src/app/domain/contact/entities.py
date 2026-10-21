from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.common.entity import AuditedEntity
from app.domain.contact.values import ContactDetails, ContactId, ContactKind

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Contact(AuditedEntity[ContactId]):
    """고객 또는 파트너 담당자. 종류는 만든 뒤 바꾸지 않는다."""

    kind: ContactKind
    details: ContactDetails

    @classmethod
    def create(
        cls,
        kind: ContactKind,
        details: ContactDetails,
        now: datetime,
        *,
        entity_id: ContactId,
    ) -> Self:
        return cls(
            id=entity_id,
            kind=kind,
            details=details,
            created_at=now,
            updated_at=now,
        )

    def update(self, details: ContactDetails, now: datetime) -> None:
        self._touch(now)
        self.details = details
