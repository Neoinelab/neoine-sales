"""등록·수정 폼의 '반영 후' 값.

등록은 입력 그대로, 수정은 현재 Deal 위에 보낸 필드를 덮어쓴 값이다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.deal.inputs import ContactDraftInput
from app.domain.bant.values import BantCategory

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date
    from uuid import UUID

    from app.application.deal.inputs import DealCreateInput, DealPatchInput
    from app.domain.deal.entities import Deal
    from app.domain.deal.values import PocState, QuoteSubmitted

ALL_FIELDS = frozenset(
    {
        "name",
        "owner_user_id",
        "vendor",
        "solution",
        "users",
        "status_key",
        "forecast_key",
        "revenue_amount",
        "revenue_date",
        "customer",
        "partner",
        "quote_submitted",
        "quote_submitted_date",
        "poc_state",
        "poc_completed_date",
        "procurement",
        "bant",
    }
)
_EMPTY_DRAFT = ContactDraftInput(None, "", "", None, None, None)


@dataclass(frozen=True, slots=True)
class FormValues:
    name: str
    owner_user_id: UUID | None
    vendor: str
    solution: str
    users: int | None
    status_key: str
    forecast_key: str
    revenue_amount: int | None
    revenue_date: date | None
    customer: ContactDraftInput | None
    partner: ContactDraftInput | None
    quote_submitted: QuoteSubmitted | None
    quote_submitted_date: date | None
    poc_state: PocState | None
    poc_completed_date: date | None
    procurement: str
    bant: Mapping[BantCategory, UUID | None]

    @classmethod
    def of_create(cls, data: DealCreateInput) -> FormValues:
        return cls(
            name=data.name,
            owner_user_id=data.owner_user_id,
            vendor=data.vendor,
            solution=data.solution,
            users=data.users,
            status_key=data.status_key,
            forecast_key=data.forecast_key,
            revenue_amount=data.revenue_amount,
            revenue_date=data.revenue_date,
            customer=data.customer,
            partner=data.partner,
            quote_submitted=data.quote_submitted,
            quote_submitted_date=data.quote_submitted_date,
            poc_state=data.poc_state,
            poc_completed_date=data.poc_completed_date,
            procurement=data.procurement,
            bant=data.bant,
        )

    @classmethod
    def of_patch(cls, deal: Deal, patch: DealPatchInput) -> FormValues:
        """현재 Deal 위에 보낸 필드만 덮어쓴다. 보내지 않은 연락처는 None(건드리지 않음)이다."""
        sent = patch.provided
        details, sync = deal.details, deal.sync
        current_bant: Mapping[BantCategory, UUID | None] = {
            c: deal.bant.get(c) for c in BantCategory
        }

        def pick[T](field: str, patched: T, current: T) -> T:
            return patched if field in sent else current

        return cls(
            name=pick("name", patch.name or "", details.name),
            owner_user_id=pick("owner_user_id", patch.owner_user_id, details.owner_user_id),
            vendor=pick("vendor", patch.vendor or "", details.vendor),
            solution=pick("solution", patch.solution or "", details.solution),
            users=pick("users", patch.users, details.users),
            status_key=pick("status_key", patch.status_key or "", sync.status_key),
            forecast_key=pick("forecast_key", patch.forecast_key or "", sync.forecast_key),
            revenue_amount=pick(
                "revenue_amount", patch.revenue_amount, details.revenue_amount.value
            ),
            revenue_date=pick("revenue_date", patch.revenue_date, details.revenue_date),
            customer=(patch.customer or _EMPTY_DRAFT) if "customer" in sent else None,
            partner=patch.partner if "partner" in sent else None,
            quote_submitted=pick("quote_submitted", patch.quote_submitted, details.quote.submitted),
            quote_submitted_date=pick(
                "quote_submitted_date", patch.quote_submitted_date, details.quote.submitted_date
            ),
            poc_state=pick("poc_state", patch.poc_state, details.poc.state),
            poc_completed_date=pick(
                "poc_completed_date", patch.poc_completed_date, details.poc.completed_date
            ),
            procurement=pick("procurement", patch.procurement or "", details.procurement),
            bant=pick("bant", patch.bant or {}, current_bant),
        )
