"""Deal 요청 스키마. 형식(타입·모르는 필드)만 검사하고 범위·길이는 도메인 문구가 나가도록 맡긴다."""

from datetime import date
from typing import Any, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from app.application.choice import CatalogChoice
from app.application.deal.inputs import ContactDraftInput, DealCreateInput, DealPatchInput
from app.domain.bant.values import BantCategory
from app.domain.deal.values import PocState, QuoteSubmitted
from app.domain.user.value_objects import UserId
from app.web.schemas.choice import CatalogChoiceRequest
from app.web.schemas.common import RequestModel
from app.web.schemas.deal_change import DealChangeRequest
from app.web.schemas.deal_search import FORECAST_KEYS_MAX, STATUS_KEY_MAX, DealSearchParams
from app.web.schemas.ids import BodyId

__all__ = [
    "FORECAST_KEYS_MAX",
    "STATUS_KEY_MAX",
    "BantRequest",
    "ContactDraftRequest",
    "DealChangeRequest",
    "DealCreateRequest",
    "DealPatchRequest",
    "DealSearchParams",
    "PocRequest",
    "QuoteRequest",
]

PATCH_SECTIONS = frozenset({"quote", "poc", "bant", "customer", "partner"})
NOT_DEAL_FIELDS = frozenset({"delete_license_contracts"})  # provided(폼 필드)에 들지 않는다


class ContactDraftRequest(RequestModel):
    """Deal 화면의 연락처 입력. contact_id가 있으면 그 연락처를 골라 입력값으로 갱신한다."""

    contact_id: BodyId | None = None
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
    owner_user_id: BodyId
    vendor_id: BodyId
    product: str | None = None
    users: StrictInt
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
            owner_user_id=UserId(self.owner_user_id),
            vendor_id=self.vendor_id,
            product=self.product if self.product is not None else "",
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
    owner_user_id: BodyId | None = None
    vendor_id: BodyId | None = None
    product: str | None = None
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
    delete_license_contracts: StrictBool = False

    @model_validator(mode="after")
    def _sections_are_not_null(self) -> Self:
        for name in ("quote", "poc", "bant"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name}은 null일 수 없습니다")
        return self

    def to_input(self) -> DealPatchInput:
        sent = self.model_fields_set
        provided = set(sent - PATCH_SECTIONS - NOT_DEAL_FIELDS)
        values: dict[str, Any] = {name: getattr(self, name) for name in provided}
        for section in ("customer", "partner"):
            if section in sent:
                provided.add(section)
                draft = getattr(self, section)
                values[section] = draft.to_input() if draft else None
        for name, part in self._parts().items():
            provided.add(name)
            values[name] = part
        return DealPatchInput(
            provided=frozenset(provided),
            delete_license_contracts=self.delete_license_contracts,
            **values,
        )

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
