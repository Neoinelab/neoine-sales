from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.money import Money
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.stage import DealStage, StageChanger
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


@dataclass(frozen=True, slots=True)
class StageChangeInput:
    """단계 변경 입력(원시 타입). 변경자는 호출자가 로그인 주체에서 꺼낸 문자열로 준다."""

    stage: DealStage
    reason: str | None
    changed_by_subject: str
    changed_by_name: str

    def to_changer(self) -> StageChanger:
        return StageChanger(subject=self.changed_by_subject, name=self.changed_by_name)
