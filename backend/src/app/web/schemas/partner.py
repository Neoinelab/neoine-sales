from typing import Annotated

from pydantic import Field

from app.application.partner.inputs import PartnerInput
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.application.ports.partner_repository import KEYWORD_MAX, PartnerQuery
from app.domain.partner.entities import Partner
from app.web.schemas.common import Page, RequestModel, ResponseModel


class PartnerRequest(RequestModel):
    company_name: str
    contact_name: str
    contact_title: str | None = None
    email: str | None = None
    phone: str | None = None

    def to_input(self) -> PartnerInput:
        return PartnerInput(**self.model_dump())


class PartnerResponse(ResponseModel):
    company_name: str
    contact_name: str
    contact_title: str | None
    email: str | None
    phone: str | None

    @classmethod
    def from_entity(cls, partner: Partner) -> PartnerResponse:
        details = partner.details
        return cls(
            id=str(partner.id),
            created_at=partner.created_at,
            updated_at=partner.updated_at,
            company_name=details.company_name,
            contact_name=details.contact_name,
            contact_title=details.contact_title,
            email=details.email.value if details.email else None,
            phone=details.phone.value if details.phone else None,
        )


class PartnerSearchParams(RequestModel):
    """파트너 목록 검색 쿼리 파라미터. 알 수 없는 파라미터는 422다."""

    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT

    def to_query(self) -> PartnerQuery:
        return PartnerQuery(**self.model_dump())


PartnerPage = Page[PartnerResponse]
