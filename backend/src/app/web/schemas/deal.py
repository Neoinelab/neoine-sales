from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.application.deal.inputs import DealInput
from app.application.ports.deal_repository import KEYWORD_MAX, DealQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.entities import Deal
from app.domain.deal.value_objects import OWNER_MAX, VENDOR_MAX
from app.domain.partner.value_objects import PartnerId
from app.web.schemas.common import Page, RequestModel, ResponseModel


class DealRequest(RequestModel):
    code: str
    name: str
    owner: str
    vendor: str
    solution: str
    revenue_amount: Decimal
    revenue_date: date
    customer_id: UUID
    partner_id: UUID | None = None
    revenue_currency: str = "KRW"

    def to_input(self) -> DealInput:
        return DealInput(**self.model_dump())


class DealResponse(ResponseModel):
    code: str
    name: str
    owner: str
    vendor: str
    solution: str
    revenue_amount: str  # 문자열: JSON 숫자로 보내면 소수 정밀도가 깨질 수 있다
    revenue_currency: str
    revenue_date: date
    customer_id: str
    partner_id: str | None

    @classmethod
    def from_entity(cls, deal: Deal) -> DealResponse:
        details = deal.details
        return cls(
            id=str(deal.id),
            created_at=deal.created_at,
            updated_at=deal.updated_at,
            code=details.code.value,
            name=details.name,
            owner=details.owner,
            vendor=details.vendor,
            solution=details.solution,
            revenue_amount=format(details.revenue.amount.normalize(), "f"),
            revenue_currency=details.revenue.currency,
            revenue_date=details.revenue_date,
            customer_id=str(details.customer_id),
            partner_id=str(details.partner_id) if details.partner_id else None,
        )


class DealSearchParams(RequestModel):
    """Deal 목록 검색 쿼리 파라미터. 매출일 기간은 revenue_from 이상, revenue_to 미만이다."""

    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    customer_id: UUID | None = None
    partner_id: UUID | None = None
    owner: Annotated[str | None, Field(max_length=OWNER_MAX)] = None
    vendor: Annotated[str | None, Field(max_length=VENDOR_MAX)] = None
    revenue_from: date | None = None
    revenue_to: date | None = None
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT

    def to_query(self) -> DealQuery:
        criteria = self.model_dump(exclude={"customer_id", "partner_id"})
        return DealQuery(
            customer_id=CustomerId(self.customer_id) if self.customer_id else None,
            partner_id=PartnerId(self.partner_id) if self.partner_id else None,
            **criteria,
        )


DealPage = Page[DealResponse]
