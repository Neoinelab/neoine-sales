from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.contact.entities import Contact


@dataclass(frozen=True, slots=True)
class ContactUsage:
    """연락처와 그것을 참조하는 Deal 수."""

    contact: Contact
    deal_count: int


@dataclass(frozen=True, slots=True)
class ContactPage:
    items: list[ContactUsage]
    total: int
    offset: int
    limit: int
