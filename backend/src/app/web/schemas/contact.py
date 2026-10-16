from typing import Annotated

from pydantic import Field

from app.application.contact.dto import ContactPage, ContactUsage
from app.application.contact.inputs import ContactInput
from app.application.ports.contact_repository import KEYWORD_MAX, ContactQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.contact.entities import Contact
from app.domain.contact.values import COMPANY_MAX, ContactKind
from app.web.schemas.common import CountedPage, RequestModel, ResponseModel


class ContactCreateRequest(RequestModel):
    """값 검증(공백·빈 값·형식)은 도메인이 한다. pydantic strip·min_length를 두지 않는다."""

    kind: ContactKind
    company: str
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None

    def to_input(self) -> ContactInput:
        return ContactInput(**self.model_dump())


class ContactUpdateRequest(RequestModel):
    """종류(kind)는 바꿀 수 없어 본문에 받지 않는다(보내면 422)."""

    company: str
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None

    def to_input(self) -> ContactInput:
        return ContactInput(kind=None, **self.model_dump())


class ContactResponse(ResponseModel):
    kind: ContactKind
    company: str
    name: str
    title: str | None
    email: str | None
    phone: str | None

    @classmethod
    def from_entity(cls, contact: Contact) -> ContactResponse:
        details = contact.details
        return cls(
            id=str(contact.id),
            created_at=contact.created_at,
            updated_at=contact.updated_at,
            kind=contact.kind,
            company=details.company,
            name=details.name,
            title=details.title,
            email=details.email.value if details.email else None,
            phone=details.phone.value if details.phone else None,
        )


class ContactRowResponse(ContactResponse):
    deal_count: int

    @classmethod
    def from_usage(cls, usage: ContactUsage) -> ContactRowResponse:
        base = ContactResponse.from_entity(usage.contact)
        return cls(**base.model_dump(), deal_count=usage.deal_count)


ContactRowPage = CountedPage[ContactRowResponse]


def row_page(page: ContactPage) -> ContactRowPage:
    return ContactRowPage(
        items=[ContactRowResponse.from_usage(u) for u in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


class ContactSearchParams(RequestModel):
    """연락처 목록 검색 쿼리 파라미터. 알 수 없는 파라미터는 422다."""

    kind: ContactKind | None = None
    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT

    def to_query(self) -> ContactQuery:
        return ContactQuery(**self.model_dump())


class CompaniesParams(RequestModel):
    kind: ContactKind


class ByCompanyParams(RequestModel):
    kind: ContactKind
    company: Annotated[str, Field(max_length=COMPANY_MAX)]
