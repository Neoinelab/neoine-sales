"""Deal 응답 스키마. 도메인 객체를 그대로 노출하지 않고 화면 계약 모양으로 바꾼다."""

from datetime import date
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, Field

from app.domain.bant.values import BantCategory
from app.domain.deal.history import HistoryCategory
from app.domain.deal.values import PocState, QuoteSubmitted
from app.domain.deal_action.next_action_status import NextActionStatus
from app.web.schemas.common import CountedPage
from app.web.schemas.contact import ContactResponse
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef

if TYPE_CHECKING:
    from app.application.deal.dto import DealPage, DealView, HistoryEntryView, NamedRef
    from app.domain.deal.entities import PartnerLink


class PartnerLinkResponse(BaseModel):
    contact_id: int
    active: bool
    linked_at: ServerDateTime
    unlinked_at: ServerDateTime | None

    @classmethod
    def from_link(cls, link: PartnerLink) -> PartnerLinkResponse:
        return cls(
            contact_id=link.contact_id,
            active=link.active,
            linked_at=link.linked_at,
            unlinked_at=link.unlinked_at,
        )


class PartnerHistoryResponse(BaseModel):
    contact: ContactResponse
    active: bool
    linked_at: ServerDateTime
    unlinked_at: ServerDateTime | None


class NextActionResponse(BaseModel):
    text: str
    due_date: date
    status: NextActionStatus


class QuoteResponse(BaseModel):
    submitted: QuoteSubmitted | None
    submitted_date: date | None


class PocResponse(BaseModel):
    state: PocState | None
    completed_date: date | None


class BantResponse(BaseModel):
    budget: int | None
    authority: int | None
    need: int | None
    timeline: int | None


class NamedRefResponse(BaseModel):
    id: int
    name: str


class DealRowResponse(BaseModel):
    code: str
    name: str
    owner_user_id: int
    owner: UserRef
    vendor: NamedRefResponse | None
    solution: str
    users: int
    status_key: str
    forecast_key: str
    revenue_amount: int  # JSON 정수(2^53-1 이하가 도메인에서 보장된다)
    revenue_date: date
    customer: ContactResponse
    active_partner: ContactResponse | None
    partner_links: list[PartnerLinkResponse]
    quote: QuoteResponse
    poc: PocResponse
    procurement: str
    bant: BantResponse
    next_action: NextActionResponse | None
    last_updated_at: Annotated[
        ServerDateTime,
        Field(
            description=(
                "모든 Action 중 가장 최근 수행 시각. Action이 없으면 Deal 등록 시각. "
                "Deal 수정은 반영하지 않는다."
            )
        ),
    ]
    risk: Literal["overdue", "stale", "overdue_stale"] | None
    status_changed_at: ServerDateTime
    status_days: int
    created_at: ServerDateTime
    updated_at: ServerDateTime

    @classmethod
    def from_view(cls, view: DealView) -> DealRowResponse:
        return cls(**_row_fields(view))


class DealDetailResponse(DealRowResponse):
    partner_history: list[PartnerHistoryResponse]

    @classmethod
    def from_view(cls, view: DealView) -> DealDetailResponse:
        """파트너 이력은 활성·비활성 링크 전체를 최근 연결 순으로 준다."""
        numbered = enumerate(view.item.deal.partner_links)
        newest_first = sorted(numbered, key=lambda pair: (pair[1].linked_at, pair[0]), reverse=True)
        links = [link for _, link in newest_first]
        history = [
            PartnerHistoryResponse(
                contact=ContactResponse.from_entity(view.partner_contacts[link.contact_id]),
                active=link.active,
                linked_at=link.linked_at,
                unlinked_at=link.unlinked_at,
            )
            for link in links
        ]
        return cls(**_row_fields(view), partner_history=history)


def _row_fields(view: DealView) -> dict[str, object]:
    deal = view.item.deal
    details = deal.details
    active_id = deal.active_partner_id()
    next_action = view.item.next_action
    return {
        "code": deal.id.value,
        "name": details.name,
        "owner_user_id": details.owner_user_id,
        "owner": UserRef.from_domain(view.owner),
        "vendor": _named(view.vendor),
        "solution": details.solution,
        "users": details.users,
        "status_key": deal.sync.status_key,
        "forecast_key": deal.sync.forecast_key,
        "revenue_amount": details.revenue_amount.value,
        "revenue_date": details.revenue_date,
        "customer": ContactResponse.from_entity(view.customer),
        "active_partner": (
            ContactResponse.from_entity(view.partner_contacts[active_id])
            if active_id is not None
            else None
        ),
        "partner_links": [PartnerLinkResponse.from_link(link) for link in deal.partner_links],
        "quote": QuoteResponse(
            submitted=details.quote.submitted, submitted_date=details.quote.submitted_date
        ),
        "poc": PocResponse(state=details.poc.state, completed_date=details.poc.completed_date),
        "procurement": details.procurement,
        "bant": BantResponse(
            **{category.value: deal.bant.get(category) for category in BantCategory}
        ),
        "next_action": (
            NextActionResponse(
                text=next_action.text, due_date=next_action.due_date, status=next_action.status
            )
            if next_action
            else None
        ),
        "last_updated_at": view.item.last_updated_at,
        "risk": None if view.risk is None else view.risk.value,
        "status_changed_at": deal.status_changed_at,
        "status_days": view.status_days,
        "created_at": deal.created_at,
        "updated_at": deal.updated_at,
    }


def _named(ref: NamedRef | None) -> NamedRefResponse | None:
    return None if ref is None else NamedRefResponse(id=ref.id, name=ref.name)


DealRowPage = CountedPage[DealRowResponse]


def row_page(page: DealPage) -> DealRowPage:
    return DealRowPage(
        items=[DealRowResponse.from_view(view) for view in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


class HistoryEntryResponse(BaseModel):
    id: int
    deal_code: str
    at: ServerDateTime
    by: UserRef
    category: HistoryCategory
    target: str
    before: str
    after: str

    @classmethod
    def from_view(cls, view: HistoryEntryView) -> HistoryEntryResponse:
        entry = view.entry
        return cls(
            id=entry.id,
            deal_code=entry.deal_code.value,
            at=entry.changed_at,
            by=UserRef.from_domain(view.by),
            category=entry.draft.category,
            target=entry.draft.target,
            before=entry.draft.before,
            after=entry.draft.after,
        )


class DeletionImpactResponse(BaseModel):
    history_count: int
    action_count: int
    attachment_count: int
    partner_meeting_count: int
