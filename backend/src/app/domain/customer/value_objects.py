from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType
from uuid import UUID

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, optional_text, required_text

if TYPE_CHECKING:
    from app.domain.common.contact import Email, PhoneNumber

CustomerId = NewType("CustomerId", UUID)

COMPANY_NAME_MAX = 200
CONTACT_NAME_MAX = 100
CONTACT_TITLE_MAX = 100
NOTES_MAX = 2000


@dataclass(frozen=True, slots=True)
class CustomerDetails:
    """고객 정보. 회사명·담당자명만 필수이고 나머지는 알 때만 채운다."""

    company_name: str
    contact_name: str
    contact_title: str | None = None
    email: Email | None = None
    phone: PhoneNumber | None = None
    employee_count: int | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.employee_count is not None and self.employee_count < 0:
            raise InvalidValueError("직원수는 0 이상이어야 합니다")
        assign(
            self,
            company_name=required_text(self.company_name, "회사명", max_length=COMPANY_NAME_MAX),
            contact_name=required_text(self.contact_name, "담당자명", max_length=CONTACT_NAME_MAX),
            contact_title=optional_text(
                self.contact_title, "담당자 직함", max_length=CONTACT_TITLE_MAX
            ),
            notes=optional_text(self.notes, "비고", max_length=NOTES_MAX) or "",
        )
