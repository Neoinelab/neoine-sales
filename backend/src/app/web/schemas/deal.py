from datetime import date
from decimal import Decimal
from uuid import UUID

from app.application.deal.inputs import DealInput
from app.domain.deal.entities import Deal
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


DealPage = Page[DealResponse]
