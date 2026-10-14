from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import Field

from app.application.deal.inputs import DealInput
from app.application.ports.deal_repository import KEYWORD_MAX, DealQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.entities import Deal
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import VENDOR_MAX
from app.domain.partner.value_objects import PartnerId
from app.domain.user.value_objects import UserId
from app.web.schemas.common import Page, RequestModel, ResponseModel
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class DealRequest(RequestModel):
    code: str
    name: str
    owner_user_id: UUID
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
    owner: UserRef
    vendor: str
    solution: str
    revenue_amount: str  # 문자열: JSON 숫자로 보내면 소수 정밀도가 깨질 수 있다
    revenue_currency: str
    revenue_date: date
    customer_id: str
    partner_id: str | None
    stage: DealStage

    @classmethod
    def from_entity(cls, deal: Deal, refs: Mapping[UserId, DomainUserRef]) -> DealResponse:
        details = deal.details
        return cls(
            id=str(deal.id),
            created_at=deal.created_at,
            updated_at=deal.updated_at,
            code=details.code.value,
            name=details.name,
            owner=ref_of(refs, details.owner_user_id),
            vendor=details.vendor,
            solution=details.solution,
            revenue_amount=format(details.revenue.amount.normalize(), "f"),
            revenue_currency=details.revenue.currency,
            revenue_date=details.revenue_date,
            customer_id=str(details.customer_id),
            partner_id=str(details.partner_id) if details.partner_id else None,
            stage=deal.stage,
        )


class DealSearchParams(RequestModel):
    """Deal 목록 검색 쿼리 파라미터. 매출일 기간은 revenue_from 이상, revenue_to 미만이다."""

    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    customer_id: UUID | None = None
    partner_id: UUID | None = None
    owner_user_id: UserId | None = None
    vendor: Annotated[str | None, Field(max_length=VENDOR_MAX)] = None
    revenue_from: date | None = None
    revenue_to: date | None = None
    stage: DealStage | None = None
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT
    mine: bool = False

    def to_query(self, viewer_user_id: UserId) -> DealQuery:
        """mine=true는 담당자가 나인 딜이다(owner_user_id보다 우선)."""
        criteria = self.model_dump(exclude={"customer_id", "partner_id", "mine", "owner_user_id"})
        return DealQuery(
            owner_user_id=viewer_user_id if self.mine else self.owner_user_id,
            customer_id=CustomerId(self.customer_id) if self.customer_id else None,
            partner_id=PartnerId(self.partner_id) if self.partner_id else None,
            **criteria,
        )


DealPage = Page[DealResponse]


async def deal_responses(provider: UseCaseProvider, deals: Sequence[Deal]) -> list[DealResponse]:
    """담당자 표시 이름을 한 번에 풀어 응답 목록을 만든다(퇴사자는 label에 (퇴사))."""
    refs = await resolve_refs(provider, [d.details.owner_user_id for d in deals])
    return [DealResponse.from_entity(d, refs) for d in deals]


async def deal_response(provider: UseCaseProvider, deal: Deal) -> DealResponse:
    (item,) = await deal_responses(provider, [deal])
    return item
