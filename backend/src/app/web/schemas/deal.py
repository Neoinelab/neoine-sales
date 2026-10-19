"""Deal 요청 스키마. 형식(타입·모르는 필드)만 검사하고 범위·길이는 도메인 문구가 나가도록 맡긴다."""

from datetime import date
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import Field, StrictInt, model_validator

from app.application.choice import CatalogChoice
from app.application.deal.inputs import ContactDraftInput, DealCreateInput, DealPatchInput
from app.application.ports.deal_repository import (
    DEFAULT_PAGE_SIZE,
    KEYWORD_MAX,
    DealQuery,
    DealSort,
    SortOrder,
)
from app.application.ports.pagination import MAX_LIMIT
from app.domain.bant.values import BantCategory
from app.domain.deal.values import PocState, QuoteSubmitted
from app.domain.user.value_objects import UserId
from app.web.schemas.choice import CatalogChoiceRequest
from app.web.schemas.common import RequestModel
from app.web.schemas.deal_change import DealChangeRequest

__all__ = [
    "BantRequest",
    "ContactDraftRequest",
    "DealChangeRequest",
    "DealCreateRequest",
    "DealPatchRequest",
    "DealSearchParams",
    "PocRequest",
    "QuoteRequest",
]

STATUS_KEY_MAX = 50
PATCH_SECTIONS = frozenset({"quote", "poc", "bant", "customer", "partner"})


class ContactDraftRequest(RequestModel):
    """Deal 화면의 연락처 입력. contact_id가 있으면 그 연락처를 골라 입력값으로 갱신한다."""

    contact_id: UUID | None = None
    company: str
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None

    def to_input(self) -> ContactDraftInput:
        return ContactDraftInput(**self.model_dump())


class QuoteRequest(RequestModel):
    submitted: QuoteSubmitted | None = None
    submitted_date: date | None = None


class PocRequest(RequestModel):
    state: PocState | None = None
    completed_date: date | None = None


class BantRequest(RequestModel):
    """구분별 BANT Label 선택 객체({id} 또는 {name}). 보내지 않았거나 null이면 선택 안 함이다."""

    budget: CatalogChoiceRequest | None = None
    authority: CatalogChoiceRequest | None = None
    need: CatalogChoiceRequest | None = None
    timeline: CatalogChoiceRequest | None = None

    def to_selection(self) -> dict[BantCategory, CatalogChoice | None]:
        chosen: dict[BantCategory, CatalogChoice | None] = {}
        for category in BantCategory:
            item: CatalogChoiceRequest | None = getattr(self, category.value)
            chosen[category] = item.to_choice() if item is not None else None
        return chosen


class DealCreateRequest(RequestModel):
    name: str
    owner_user_id: UUID
    vendor_id: UUID | None = None
    solution_id: UUID | None = None
    users: StrictInt | None = None
    status_key: str
    forecast_key: str
    revenue_amount: StrictInt
    revenue_date: date | None
    customer: ContactDraftRequest
    partner: ContactDraftRequest | None = None
    quote: QuoteRequest = Field(default_factory=QuoteRequest)
    poc: PocRequest = Field(default_factory=PocRequest)
    procurement: str = ""
    bant: BantRequest = Field(default_factory=BantRequest)

    def to_input(self) -> DealCreateInput:
        return DealCreateInput(
            name=self.name,
            owner_user_id=self.owner_user_id,
            vendor_id=self.vendor_id,
            solution_id=self.solution_id,
            users=self.users,
            status_key=self.status_key,
            forecast_key=self.forecast_key,
            revenue_amount=self.revenue_amount,
            revenue_date=self.revenue_date,
            customer=self.customer.to_input(),
            partner=self.partner.to_input() if self.partner else None,
            quote_submitted=self.quote.submitted,
            quote_submitted_date=self.quote.submitted_date,
            poc_state=self.poc.state,
            poc_completed_date=self.poc.completed_date,
            procurement=self.procurement,
            bant=self.bant.to_selection(),
        )


class DealPatchRequest(RequestModel):
    """수정 본문. 보낸 필드만 반영한다(model_fields_set). partner: null은 활성 파트너 제거다."""

    name: str | None = None
    owner_user_id: UUID | None = None
    vendor_id: UUID | None = None
    solution_id: UUID | None = None
    users: StrictInt | None = None
    status_key: str | None = None
    forecast_key: str | None = None
    revenue_amount: StrictInt | None = None
    revenue_date: date | None = None
    customer: ContactDraftRequest | None = None
    partner: ContactDraftRequest | None = None
    quote: QuoteRequest | None = None
    poc: PocRequest | None = None
    bant: BantRequest | None = None
    procurement: str | None = None

    @model_validator(mode="after")
    def _sections_are_not_null(self) -> Self:
        for name in ("quote", "poc", "bant"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name}은 null일 수 없습니다")
        return self

    def to_input(self) -> DealPatchInput:
        sent = self.model_fields_set
        provided = set(sent - PATCH_SECTIONS)
        values: dict[str, Any] = {name: getattr(self, name) for name in provided}
        for section in ("customer", "partner"):
            if section in sent:
                provided.add(section)
                draft = getattr(self, section)
                values[section] = draft.to_input() if draft else None
        for name, part in self._parts().items():
            provided.add(name)
            values[name] = part
        return DealPatchInput(provided=frozenset(provided), **values)

    def _parts(self) -> dict[str, Any]:
        """quote·poc·bant를 유스케이스 입력 필드로 펼친다(보낸 객체의 하위 필드는 모두 보낸 값)."""
        parts: dict[str, Any] = {}
        if self.quote is not None:
            parts["quote_submitted"] = self.quote.submitted
            parts["quote_submitted_date"] = self.quote.submitted_date
        if self.poc is not None:
            parts["poc_state"] = self.poc.state
            parts["poc_completed_date"] = self.poc.completed_date
        if self.bant is not None:
            parts["bant"] = self.bant.to_selection()
        return parts


class DealSearchParams(RequestModel):
    """Deal 목록 검색 쿼리 파라미터. 기간은 양끝을 포함한다. mine=true가 owner_user_id보다 우선."""

    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    owner_user_id: UserId | None = None
    mine: bool = False
    vendor_id: UUID | None = None
    solution_id: UUID | None = None
    status_key: Annotated[str | None, Field(max_length=STATUS_KEY_MAX)] = None
    forecast_key: Annotated[str | None, Field(max_length=STATUS_KEY_MAX)] = None
    year: Annotated[int | None, Field(ge=1900, le=9999)] = None
    quarter: Annotated[int | None, Field(ge=1, le=4)] = None
    revenue_from: date | None = None
    revenue_to: date | None = None
    bant_budget: UUID | None = None
    bant_authority: UUID | None = None
    bant_need: UUID | None = None
    bant_timeline: UUID | None = None
    sort: DealSort = DealSort.LAST_UPDATED_AT
    order: SortOrder = SortOrder.DESC
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_PAGE_SIZE

    def to_query(self, viewer_user_id: UserId) -> DealQuery:
        bant_fields = {category: f"bant_{category.value}" for category in BantCategory}
        criteria = self.model_dump(exclude={"mine", "owner_user_id", *bant_fields.values()})
        bant = {
            category: getattr(self, name)
            for category, name in bant_fields.items()
            if getattr(self, name) is not None
        }
        return DealQuery(
            owner_user_id=viewer_user_id if self.mine else self.owner_user_id,
            bant_label_ids=bant,
            **criteria,
        )
