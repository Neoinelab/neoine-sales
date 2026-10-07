from app.application.customer.inputs import CustomerInput
from app.domain.customer.entities import Customer
from app.web.schemas.common import Page, RequestModel, ResponseModel


class CustomerRequest(RequestModel):
    company_name: str
    contact_name: str
    contact_title: str | None = None
    email: str | None = None
    phone: str | None = None
    employee_count: int | None = None
    notes: str = ""

    def to_input(self) -> CustomerInput:
        return CustomerInput(**self.model_dump())


class CustomerResponse(ResponseModel):
    company_name: str
    contact_name: str
    contact_title: str | None
    email: str | None
    phone: str | None
    employee_count: int | None
    notes: str

    @classmethod
    def from_entity(cls, customer: Customer) -> CustomerResponse:
        details = customer.details
        return cls(
            id=str(customer.id),
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            company_name=details.company_name,
            contact_name=details.contact_name,
            contact_title=details.contact_title,
            email=details.email.value if details.email else None,
            phone=details.phone.value if details.phone else None,
            employee_count=details.employee_count,
            notes=details.notes,
        )


CustomerPage = Page[CustomerResponse]
