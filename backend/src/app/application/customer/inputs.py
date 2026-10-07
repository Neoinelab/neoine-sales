from dataclasses import dataclass

from app.domain.common.contact import Email, PhoneNumber
from app.domain.customer.value_objects import CustomerDetails


@dataclass(frozen=True, slots=True)
class CustomerInput:
    """고객 등록·수정 입력(원시 타입). 형식 검증은 도메인 값 객체가 한다."""

    company_name: str
    contact_name: str
    contact_title: str | None = None
    email: str | None = None
    phone: str | None = None
    employee_count: int | None = None
    notes: str = ""

    def to_details(self) -> CustomerDetails:
        return CustomerDetails(
            company_name=self.company_name,
            contact_name=self.contact_name,
            contact_title=self.contact_title,
            email=Email(self.email) if self.email and self.email.strip() else None,
            phone=PhoneNumber(self.phone) if self.phone and self.phone.strip() else None,
            employee_count=self.employee_count,
            notes=self.notes,
        )
