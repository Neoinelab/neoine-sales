from typing import Annotated

from pydantic import Field

from app.application.customer.inputs import CustomerInput
from app.application.ports.customer_repository import KEYWORD_MAX, CustomerQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
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


class CustomerSearchParams(RequestModel):
    """고객 목록 검색 쿼리 파라미터. 알 수 없는 파라미터는 422다."""

    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT

    def to_query(self) -> CustomerQuery:
        return CustomerQuery(**self.model_dump())


CustomerPage = Page[CustomerResponse]
