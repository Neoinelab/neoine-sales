from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.common.entity import AuditedEntity
from app.domain.vendor.errors import VendorInUseError
from app.domain.vendor.values import VendorId

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Vendor(AuditedEntity[VendorId]):
    """Aggregate Root. 이름은 대소문자 무시로 고유하다(고유성은 `rules`가 확인한다)."""

    name: str

    @classmethod
    def create(cls, *, entity_id: VendorId, name: str, now: datetime) -> Self:
        """이름은 이미 정규화된 값이다."""
        return cls(id=entity_id, name=name, created_at=now, updated_at=now)

    def rename(self, name: str, now: datetime) -> None:
        self.name = name
        self._touch(now)

    def ensure_deletable(self, usage: int) -> None:
        """usage는 이 Vendor를 쓰는 Deal 수."""
        if usage > 0:
            raise VendorInUseError(usage)
