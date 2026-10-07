from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.money import Money
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.value_objects import DealCode, DealDetails
from app.domain.partner.value_objects import PartnerId

if TYPE_CHECKING:
    from datetime import date
    from decimal import Decimal
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DealInput:
    """Deal 등록·수정 입력(원시 타입). 형식 검증은 도메인 값 객체가 한다."""

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

    def to_details(self) -> DealDetails:
        return DealDetails(
            code=DealCode(self.code),
            name=self.name,
            owner=self.owner,
            vendor=self.vendor,
            solution=self.solution,
            revenue=Money(self.revenue_amount, self.revenue_currency),
            revenue_date=self.revenue_date,
            customer_id=CustomerId(self.customer_id),
            partner_id=PartnerId(self.partner_id) if self.partner_id else None,
        )
