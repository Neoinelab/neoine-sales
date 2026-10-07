from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType
from uuid import UUID

from app.domain.common.validation import assign, optional_text, required_text

if TYPE_CHECKING:
    from app.domain.common.contact import Email, PhoneNumber

PartnerId = NewType("PartnerId", UUID)

COMPANY_NAME_MAX = 200
CONTACT_NAME_MAX = 100
CONTACT_TITLE_MAX = 100


@dataclass(frozen=True, slots=True)
class PartnerDetails:
    """파트너 정보. 파트너사·담당자만 필수이고 나머지는 알 때만 채운다."""

    company_name: str
    contact_name: str
    contact_title: str | None = None
    email: Email | None = None
    phone: PhoneNumber | None = None

    def __post_init__(self) -> None:
        assign(
            self,
            company_name=required_text(self.company_name, "파트너사", max_length=COMPANY_NAME_MAX),
            contact_name=required_text(self.contact_name, "담당자", max_length=CONTACT_NAME_MAX),
            contact_title=optional_text(self.contact_title, "직함", max_length=CONTACT_TITLE_MAX),
        )
